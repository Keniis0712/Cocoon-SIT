import { useEffect, useState } from "react";
import { ArrowLeft, Loader2, Trash2 } from "lucide-react";
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
  const [isDeletingId, setIsDeletingId] = useState<number | null>(null);

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
      toast.error("加载长期记忆失败");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDelete(memoryId: number) {
    setIsDeletingId(memoryId);
    try {
      await deleteCocoonMemory(cocoonId, memoryId);
      setItems((prev) => prev.filter((item) => item.id !== memoryId));
      toast.success("长期记忆已删除");
    } catch (error) {
      console.error(error);
      toast.error("删除长期记忆失败");
    } finally {
      setIsDeletingId(null);
    }
  }

  return (
    <PageFrame
      title={`${cocoon?.name || "Cocoon"} · 长期记忆`}
      description="这里单独查看当前 Cocoon 可见的长期记忆，不需要审计权限。"
      actions={
        <Button variant="outline" onClick={() => navigate(`/cocoons/${cocoonId}`)}>
          <ArrowLeft className="mr-2 size-4" />
          返回聊天
        </Button>
      }
    >
      <Card className="border-border/70 bg-card/90">
        <CardHeader>
          <CardTitle>长期记忆列表</CardTitle>
          <CardDescription>按写入时间倒序展示。删除后会同步清理对应向量条目。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              加载长期记忆中...
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              当前没有可见的长期记忆。
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
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isDeletingId === memory.id}
                    onClick={() => handleDelete(memory.id)}
                  >
                    {isDeletingId === memory.id ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
                  </Button>
                </div>
                <div className="whitespace-pre-wrap text-sm leading-6">{memory.content}</div>
                <div className="mt-3 text-xs text-muted-foreground">
                  重要度 {memory.importance} · {formatTime(memory.created_at)}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </PageFrame>
  );
}
