import { notFound } from "next/navigation";

import { ScreenTemplate } from "@/components/screens/screen-template";
import { getScreenBySlug } from "@/lib/screen-catalog";

export default async function ScreenPage({
  params
}: {
  params: Promise<{ slug: string[] }>;
}) {
  const resolvedParams = await params;
  const screen = getScreenBySlug(resolvedParams.slug);

  if (!screen) {
    notFound();
  }

  return <ScreenTemplate screen={screen} />;
}
