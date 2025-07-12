import StoreDashboard from "@/components/StoreDashboard";

export default async function StorePage({ params }) {
  const { storeId } = await params;
  return <StoreDashboard storeId={storeId} />;
}
