import type { ScreenDefinition } from "@/lib/screen-catalog";
import { getWorkspaceData } from "@/lib/workspace-service";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";
import { ScreenExperience } from "./screen-experience";

export async function ScreenTemplate({ screen }: { screen: ScreenDefinition }) {
  const snapshot = await getWorkspaceData(await getWorkspaceRequestContext());
  return <ScreenExperience screen={screen} snapshot={snapshot} />;
}
