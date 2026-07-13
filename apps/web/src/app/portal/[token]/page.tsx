import { getPublicPortalPreview } from "@/lib/server-workspace-service";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";
import { PortalExperience } from "@/components/screens/portal-experience";

export default async function PortalPage({
  params
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const preview = await getPublicPortalPreview(token, await getWorkspaceRequestContext());
  return <PortalExperience preview={preview} />;
}
