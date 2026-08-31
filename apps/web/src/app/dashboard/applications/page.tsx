"use client";

import { ApplicationsTable } from "@/components/applications/applications-table";

export default function ApplicationsPage() {
  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight">Applications</h2>
      </div>

      <ApplicationsTable />
    </div>
  );
}

