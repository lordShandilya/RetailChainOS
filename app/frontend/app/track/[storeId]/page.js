import TrackPortal from "@/components/TrackPortal";

export default async function TrackPage({ params }) {
  // console.log("params track: ", params);
  const { storeId } = await params;
  // console.log("pramas: ", par);
  return <TrackPortal storeId={storeId} />;
}
