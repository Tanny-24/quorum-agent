import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-10 text-center">
      <div className="mx-auto mb-3 grid size-9 place-items-center rounded-full bg-white text-sm font-bold text-slate-400 shadow-sm">
        ✓
      </div>
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-sm leading-5 text-muted-foreground">
        {description}
      </p>
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return (
    <Card className="border-red/20">
      <CardContent className="flex flex-col items-start gap-4 pt-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-semibold text-foreground">QUORUM API is unavailable</p>
          <p className="mt-1 text-sm text-muted-foreground">{message}</p>
        </div>
        <Button variant="outline" onClick={retry}>
          Try again
        </Button>
      </CardContent>
    </Card>
  );
}

export function StaleNotice({ message }: { message: string }) {
  return (
    <div className="mb-4 rounded-lg border border-amber/20 bg-amber-soft px-4 py-3 text-sm text-amber">
      {message} Showing the most recently loaded state.
    </div>
  );
}
