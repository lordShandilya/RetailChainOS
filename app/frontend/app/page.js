import Link from "next/link";

export default function Home() {
  return (
    <div className="container mx-auto p-6">
      <div className="hero min-h-screen bg-base-200">
        <div className="hero-content text-center">
          <div className="max-w-md">
            <h1 className="text-5xl font-bold">RetailChain OS</h1>
            <p className="py-6">
              Streamline inventory management, track deliveries in real-time,
              and optimize routes for Walmart India.
            </p>
            <div className="flex gap-4 justify-center">
              <Link href="/login" className="btn btn-primary">
                Login
              </Link>
              <Link href="/admin" className="btn btn-secondary">
                Admin Dashboard
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
