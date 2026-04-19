import { useEffect, useState } from "react";
import { ArrowLeft, Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { deleteCocoonMemory, getCocoon, getCocoonMemories } from "@/api/cocoons";
import type { CocoonRead, MemoryChunkRead } from "@/api/types";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "-";
}

export default function CocoonMemoryPage() {
  const navigate = useNavigate();
  const params = useParams();
  const cocoonId = Number(params.cocoonId);

  const [cocoon, setCocoon] = useState<CocoonRead | null>(null);
  const [items, setItems] = useState<MemoryChunkRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!Number.isFinite(cocoonId) || cocoonId <= 0) {
      navigate("/cocoons", { replace: true });
      return;
    }
    void load();
  }, [cocoonId]);

  async function load() {
    setIsLoading(true);
    try {
      const [cocoonResp, memoryResp] = await Promise.all([
        getCocoon(cocoonId),
        getCocoonMemories(cocoonId, 1, 100),
      ]);
      setCocoon(cocoonResp);
      setItems(memoryResp.items);
    } catch (error) {
      console.error(error);
      toast.error("Failed to load cocoon memories");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDeleteMemory(memory: MemoryChunkRead) {
    if (!window.confirm(`Delete memory #${memory.id}?`)) {
      return;
    }
    try {
      await deleteCocoonMemory(cocoonId, memory.id);
      setItems((prev) => prev.filter((item) => item.id !== memory.id));
      toast.success("Memory deleted");
    } catch (error) {
      console.error(error);
      toast.error(error instanceof Error ? error.message : "Failed to delete memory");
    }
  }

  return (
    <PageFrame
      title={`${cocoon?.name || "Cocoon"} / Memories`}
      description="Newest memories first. Individual memory deletion is now available."
      actions={
        <Button variant="outline" onClick={() => navigate(`/cocoons/${cocoonId}`)}>
          <ArrowLeft className="mr-2 size-4" />
          Back to chat
        </Button>
      }
    >
      <Card className="border-border/70 bg-card/90">
        <CardHeader>
          <CardTitle>Memory Chunks</CardTitle>
          <CardDescription>Review long-term memory for this cocoon and remove stale entries when needed.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              Loading memories...
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              No visible memories for this cocoon.
            </div>
          ) : (
            items.map((memory) => (
              <div key={memory.id} className="rounded-2xl border border-border/70 p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">#{memory.id}</Badge>
                    <Badge variant="secondary">{memory.source_kind}</Badge>
                    {memory.is_summary ? <Badge variant="secondary">summary</Badge> : null}
                    {(memory.tags || []).map((tag) => (
                      <Badge key={`${memory.id}-${tag}`} variant="outline">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => void handleDeleteMemory(memory)}>
                    <Trash2 className="mr-2 size-4" />
                    Delete
                  </Button>
                </div>
                <div className="whitespace-pre-wrap text-sm leading-6">{memory.content}</div>
                <div className="mt-3 text-xs text-muted-foreground">
                  Importance {memory.importance} / {formatTime(memory.created_at)}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </PageFrame>
  );
}
