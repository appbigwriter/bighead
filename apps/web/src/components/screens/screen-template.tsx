import type { ScreenDefinition } from "@/lib/screen-catalog";
import { getServerWorkspaceData } from "@/lib/server-workspace-service";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";
import { ScreenExperience } from "./screen-experience";

export async function ScreenTemplate({ screen }: { screen: ScreenDefinition }) {
  const snapshot = await getServerWorkspaceData(await getWorkspaceRequestContext());
  return <ScreenExperience screen={screen} snapshot={snapshot} />;
}
