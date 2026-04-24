from __future__ import annotations

from dataclasses import dataclass
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


@dataclass(slots=True)
class ArchivedDependency:
    name: str
    version: str
    path: Path
    size_bytes: int


@dataclass(slots=True)
class SharedPackageInventoryItem:
    name: str
    normalized_name: str
    version: str
    path: Path
    reference_count: int
    size_bytes: int


class DependencyBuilder:
    """Builds plugin dependency manifests and install roots."""

    REQUIREMENT_FILENAMES = ("requirements.txt", "requirements.lock", "requirements-dev.txt")
    _NORMALIZE_NAME_PATTERN = re.compile(r"[-_.]+")
    _PACKAGE_METADATA_FILENAME = ".package-info.json"

    def _find_requirements_file(self, extracted_root: Path) -> Path | None:
        for name in self.REQUIREMENT_FILENAMES:
            candidate = extracted_root / name
            if candidate.exists():
                return candidate
        return None

    def load_manifest(self, manifest_path: Path) -> dict:
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def _directory_size_bytes(self, root: Path) -> int:
        if not root.exists():
            return 0
        total = 0
        try:
            paths = list(root.rglob("*"))
        except FileNotFoundError:
            return 0
        for path in paths:
            try:
                if path.is_file():
                    total += path.stat().st_size
            except FileNotFoundError:
                continue
        return total

    def _normalize_distribution_name(self, name: str) -> str:
        return self._NORMALIZE_NAME_PATTERN.sub("-", name).strip("-").lower()

    def _package_metadata_path(self, package_root: Path) -> Path:
        return package_root / self._PACKAGE_METADATA_FILENAME

    def _load_package_metadata(self, package_root: Path) -> dict | None:
        metadata_path = self._package_metadata_path(package_root)
        if not metadata_path.exists():
            return None
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _write_package_metadata(
        self,
        package_root: Path,
        *,
        name: str,
        normalized_name: str,
        version: str,
        size_bytes: int,
    ) -> None:
        metadata_path = self._package_metadata_path(package_root)
        metadata_path.write_text(
            json.dumps(
                {
                    "name": name,
                    "normalized_name": normalized_name,
                    "version": version,
                    "size_bytes": int(size_bytes),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _install_to_staging(self, requirements_path: Path, staging_root: Path) -> None:
        staging_root.mkdir(parents=True, exist_ok=True)
        requirements_text = requirements_path.read_text(encoding="utf-8")
        if not requirements_text.strip():
            return
        command = self._dependency_install_command(requirements_path, staging_root)
        subprocess.run(command, check=True)

    def _dependency_install_command(self, requirements_path: Path, staging_root: Path) -> list[str]:
        pip_check = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if pip_check.returncode == 0:
            return [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--target",
                str(staging_root),
                "-r",
                str(requirements_path),
            ]
        uv_executable = shutil.which("uv")
        if uv_executable:
            return [
                uv_executable,
                "pip",
                "install",
                "--python",
                sys.executable,
                "--target",
                str(staging_root),
                "-r",
                str(requirements_path),
            ]
        raise RuntimeError("Plugin dependency installation requires pip or uv to be available")

    def _copy_distribution_files(
        self,
        *,
        staging_root: Path,
        package_root: Path,
        files: list[importlib.metadata.PackagePath],
    ) -> None:
        for package_path in files:
            relative_path = Path(str(package_path))
            source = staging_root / relative_path
            if not source.exists():
                continue
            destination = package_root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)

    def _archive_staging_distributions(
        self,
        *,
        staging_root: Path,
        shared_lib_root: Path,
    ) -> list[ArchivedDependency]:
        archived: list[ArchivedDependency] = []
        for distribution in sorted(
            importlib.metadata.distributions(path=[str(staging_root)]),
            key=lambda item: (self._normalize_distribution_name(item.metadata["Name"]), item.version),
        ):
            name = distribution.metadata["Name"]
            version = distribution.version
            normalized_name = self._normalize_distribution_name(name)
            package_root = shared_lib_root / normalized_name / version
            if not package_root.exists():
                package_root.mkdir(parents=True, exist_ok=True)
                files = list(distribution.files or [])
                if files:
                    self._copy_distribution_files(staging_root=staging_root, package_root=package_root, files=files)
                size_bytes = self._directory_size_bytes(package_root)
                self._write_package_metadata(
                    package_root,
                    name=name,
                    normalized_name=normalized_name,
                    version=version,
                    size_bytes=size_bytes,
                )
            else:
                metadata = self._load_package_metadata(package_root)
                if metadata and metadata.get("size_bytes") is not None:
                    size_bytes = int(metadata["size_bytes"])
                else:
                    size_bytes = self._directory_size_bytes(package_root)
                    self._write_package_metadata(
                        package_root,
                        name=name,
                        normalized_name=normalized_name,
                        version=version,
                        size_bytes=size_bytes,
                    )
            archived.append(ArchivedDependency(name=name, version=version, path=package_root, size_bytes=size_bytes))
        return archived

    def build(
        self,
        *,
        extracted_root: Path,
        version_root: Path,
        shared_lib_root: Path,
    ) -> Path:
        shared_lib_root.mkdir(parents=True, exist_ok=True)
        paths = [str(extracted_root)]
        packages: list[dict[str, str]] = []
        requirements_path = self._find_requirements_file(extracted_root)
        if requirements_path:
            staging_root = version_root / ".dependency_staging"
            try:
                self._install_to_staging(requirements_path, staging_root)
                archived = self._archive_staging_distributions(
                    staging_root=staging_root,
                    shared_lib_root=shared_lib_root,
                )
            finally:
                shutil.rmtree(staging_root, ignore_errors=True)
            paths = [str(item.path) for item in archived] + paths
            packages = [
                {
                    "name": item.name,
                    "normalized_name": self._normalize_distribution_name(item.name),
                    "version": item.version,
                    "path": str(item.path),
                    "size_bytes": item.size_bytes,
                }
                for item in archived
            ]
        manifest_path = version_root / "dependency_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "paths": paths,
                    "packages": packages,
                    "shared_lib_root": str(shared_lib_root),
                    "requirements_file": str(requirements_path) if requirements_path else None,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return manifest_path

    def prune_unused_packages(self, *, shared_lib_root: Path, manifest_paths: list[Path]) -> None:
        if not shared_lib_root.exists():
            return
        referenced_paths: set[Path] = set()
        for manifest_path in manifest_paths:
            if not manifest_path.exists():
                continue
            manifest = self.load_manifest(manifest_path)
            for package in manifest.get("packages") or []:
                path = package.get("path")
                if path:
                    referenced_paths.add(Path(path).resolve())
        for package_name_root in shared_lib_root.iterdir():
            if not package_name_root.is_dir():
                continue
            for version_root in list(package_name_root.iterdir()):
                if not version_root.is_dir():
                    continue
                if version_root.resolve() not in referenced_paths:
                    shutil.rmtree(version_root, ignore_errors=True)
            if not any(package_name_root.iterdir()):
                shutil.rmtree(package_name_root, ignore_errors=True)

    def collect_inventory(
        self,
        *,
        shared_lib_root: Path,
        manifest_paths: list[Path],
    ) -> list[SharedPackageInventoryItem]:
        reference_counts: dict[Path, tuple[str, str, str, int]] = {}
        for manifest_path in manifest_paths:
            if not manifest_path.exists():
                continue
            manifest = self.load_manifest(manifest_path)
            for package in manifest.get("packages") or []:
                path_value = package.get("path")
                if not path_value:
                    continue
                package_path = Path(path_value).resolve()
                name = str(package.get("name") or package_path.parent.name)
                normalized_name = str(package.get("normalized_name") or self._normalize_distribution_name(name))
                version = str(package.get("version") or package_path.name)
                size_bytes = int(package.get("size_bytes") or 0)
                _, _, _, _, current_count = reference_counts.get(package_path, (name, normalized_name, version, size_bytes, 0))
                reference_counts[package_path] = (name, normalized_name, version, size_bytes, current_count + 1)

        inventory: list[SharedPackageInventoryItem] = []
        if not shared_lib_root.exists():
            return inventory
        try:
            package_roots = list(shared_lib_root.iterdir())
        except FileNotFoundError:
            return inventory
        for package_name_root in package_roots:
            if not package_name_root.is_dir():
                continue
            try:
                version_roots = list(package_name_root.iterdir())
            except FileNotFoundError:
                continue
            for version_root in version_roots:
                if not version_root.is_dir():
                    continue
                resolved_root = version_root.resolve()
                metadata = self._load_package_metadata(version_root) or {}
                name, normalized_name, version, size_bytes, count = reference_counts.get(
                    resolved_root,
                    (
                        str(metadata.get("name") or package_name_root.name),
                        str(metadata.get("normalized_name") or package_name_root.name),
                        str(metadata.get("version") or version_root.name),
                        int(metadata.get("size_bytes") or 0),
                        0,
                    ),
                )
                if size_bytes <= 0:
                    size_bytes = self._directory_size_bytes(version_root)
                    self._write_package_metadata(
                        version_root,
                        name=name,
                        normalized_name=normalized_name,
                        version=version,
                        size_bytes=size_bytes,
                    )
                inventory.append(
                    SharedPackageInventoryItem(
                        name=name,
                        normalized_name=normalized_name,
                        version=version,
                        path=version_root,
                        reference_count=count,
                        size_bytes=size_bytes,
                    )
                )
        inventory.sort(key=lambda item: (item.normalized_name, item.version))
        return inventory
