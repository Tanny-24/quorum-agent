import { HumanDecisionsWorkspace } from "@/components/human-decisions-workspace";

export default async function HumanDecisionsPage({
  searchParams,
}: {
  searchParams: Promise<{ decision?: string }>;
}) {
  const { decision } = await searchParams;
  return <HumanDecisionsWorkspace initialDecisionId={decision} />;
}
