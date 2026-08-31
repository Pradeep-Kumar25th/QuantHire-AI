import Link from "next/link";

export function ComingSoonPanel({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="max-w-md text-muted-foreground">{description}</p>
      <Link href="/dashboard" className="text-sm text-primary underline underline-offset-4">
        Back to dashboard
      </Link>
    </div>
  );
}
