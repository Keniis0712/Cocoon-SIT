import AccessCard from "@/components/AccessCard";
import PageFrame from "@/components/PageFrame";

export default function ChatGroupsPage() {
  return (
    <PageFrame
      title="Chat Groups"
      description="The current backend does not expose chat-group management, so this page is kept only as a capability notice."
    >
      <AccessCard
        title="Not Available"
        description="Chat-group CRUD is not implemented on the current backend. The sidebar entry has been removed to avoid unsupported actions."
      />
    </PageFrame>
  );
}
