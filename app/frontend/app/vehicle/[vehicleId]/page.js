// app/vehicle/[vehicleId]/page.js
import DeliveryMap from "@/components/DeliveryMap";

export default async function VehiclePage({ params }) {
  const { vehicleId } = await params;
  return <DeliveryMap vehicleId={vehicleId} />;
}
