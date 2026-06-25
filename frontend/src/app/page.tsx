"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [status, setStatus] = useState<string>("Checking backend...");
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  useEffect(() => {
    fetch(`${apiUrl}/api/v1/health`)
      .then((res) => res.json())
      .then((data) => setStatus(JSON.stringify(data, null, 2)))
      .catch(() => setStatus("❌ Cannot reach the backend. Is it running on port 8000?"));
  }, [apiUrl]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-4xl font-bold">PrimeX AI</h1>
      <p className="text-sm text-gray-500">Backend health check:</p>
      <pre className="rounded-lg bg-gray-100 p-4 text-sm text-gray-800">{status}</pre>
    </main>
  );
}