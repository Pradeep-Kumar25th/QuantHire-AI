"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const applications = [
  {
    id: "1",
    candidate: "Alice Johnson",
    job: "Senior Software Engineer",
    status: "interviewing",
    matchScore: 92,
    appliedDate: "2024-01-15",
    stage: "Technical Interview",
  },
  {
    id: "2",
    candidate: "Bob Smith",
    job: "Frontend Developer",
    status: "screening",
    matchScore: 85,
    appliedDate: "2024-01-18",
    stage: "Initial Screening",
  },
  {
    id: "3",
    candidate: "Carol Davis",
    job: "Product Manager",
    status: "offer",
    matchScore: 88,
    appliedDate: "2024-01-10",
    stage: "Offer Sent",
  },
  {
    id: "4",
    candidate: "David Lee",
    job: "Data Scientist",
    status: "assessment",
    matchScore: 78,
    appliedDate: "2024-01-20",
    stage: "Technical Assessment",
  },
  {
    id: "5",
    candidate: "Emma Wilson",
    job: "UX Designer",
    status: "applied",
    matchScore: 81,
    appliedDate: "2024-01-22",
    stage: "Applied",
  },
];

const statusColors: Record<string, { bg: string; text: string }> = {
  applied: { bg: "bg-brand-teal/15", text: "text-brand-teal" },
  screening: { bg: "bg-brand-gold/20", text: "text-brand-dark" },
  assessment: { bg: "bg-brand-gray/20", text: "text-brand-dark" },
  interviewing: { bg: "bg-brand-dark/10", text: "text-brand-dark" },
  offer: { bg: "bg-brand-red/15", text: "text-brand-red" },
};

export function ApplicationsTable() {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Candidate</TableHead>
            <TableHead>Job</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Stage</TableHead>
            <TableHead>Match Score</TableHead>
            <TableHead>Applied Date</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {applications.map((app) => (
            <TableRow key={app.id}>
              <TableCell className="font-medium">{app.candidate}</TableCell>
              <TableCell>{app.job}</TableCell>
              <TableCell>
                <Badge
                  className={`${statusColors[app.status].bg} ${statusColors[app.status].text} capitalize`}
                >
                  {app.status}
                </Badge>
              </TableCell>
              <TableCell>{app.stage}</TableCell>
              <TableCell>
                <div className="flex items-center">
                  <span className="font-medium">{app.matchScore}%</span>
                </div>
              </TableCell>
              <TableCell>
                {new Date(app.appliedDate).toLocaleDateString()}
              </TableCell>
              <TableCell>
                <Link
                  href={`/dashboard/applications/${app.id}`}
                  className="text-primary hover:underline"
                >
                  View
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

