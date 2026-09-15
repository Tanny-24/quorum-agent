import { DecisionFeedWorkspace } from "@/components/decision-feed-workspace";

export default async function DecisionFeedPage({
  searchParams,
}: {
  searchParams: Promise<{ shift_id?: string }>;
}) {
  const { shift_id } = await searchParams;
  return <DecisionFeedWorkspace initialShiftId={shift_id} />;
}
