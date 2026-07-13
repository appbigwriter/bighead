import { notFound } from "next/navigation";

import { ScreenTemplate } from "@/components/screens/screen-template";
import { getScreenBySlug } from "@/lib/screen-catalog";

export default async function ScreenPage({
  params,
  searchParams
}: {
  params: Promise<{ slug: string[] }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolvedParams = await params;
  const screen = getScreenBySlug(resolvedParams.slug);

  if (!screen) {
    notFound();
  }

  return <ScreenTemplate screen={screen} searchParams={await searchParams} />;
}
