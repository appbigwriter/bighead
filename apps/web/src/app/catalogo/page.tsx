import { notFound } from "next/navigation";

import { CatalogPage } from "@/components/screens/catalog-page";

export default function CatalogRoute() {
  if (process.env.NODE_ENV !== "development") notFound();
  return <CatalogPage />;
}
