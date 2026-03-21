"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getSetupStatus } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    getSetupStatus().then(({ needs_setup }) => {
      router.replace(needs_setup ? "/setup" : "/projects");
    });
  }, [router]);
  return null;
}
