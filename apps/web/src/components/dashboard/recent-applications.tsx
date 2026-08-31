"use client";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

const applications = [
  {
    id: "1",
    candidate: "Alice Johnson",
    job: "Senior Software Engineer",
    status: "interviewing",
    matchScore: 92,
    appliedDays: 2,
  },
  {
    id: "2",
    candidate: "Bob Smith",
    job: "Frontend Developer",
    status: "screening",
    matchScore: 85,
    appliedDays: 1,
  },
  {
    id: "3",
    candidate: "Carol Davis",
    job: "Product Manager",
    status: "offer",
    matchScore: 88,
    appliedDays: 10,
  },
  {
    id: "4",
    candidate: "David Lee",
    job: "Data Scientist",
    status: "assessment",
    matchScore: 78,
    appliedDays: 3,
  },
  {
    id: "5",
    candidate: "Emma Wilson",
    job: "UX Designer",
    status: "applied",
    matchScore: 81,
    appliedDays: 0,
  },
];

const statusColors: Record<string, { bg: string; text: string }> = {
  applied: { bg: "bg-brand-teal", text: "text-white" },
  screening: { bg: "bg-brand-gold", text: "text-brand-dark" },
  assessment: { bg: "bg-brand-gray", text: "text-brand-dark" },
  interviewing: { bg: "bg-brand-dark", text: "text-white" },
  offer: { bg: "bg-brand-red", text: "text-white" },
};

export function RecentApplications() {
  return (
    <div className="space-y-4">
      {applications.map((app) => (
        <div
          key={app.id}
          className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer"
        >
          <div className="flex items-center space-x-4">
            <Avatar>
              <AvatarFallback>
                {app.candidate
                  .split(" ")
                  .map((n) => n[0])
                  .join("")}
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="text-sm font-medium leading-none">{app.candidate}</p>
              <p className="text-sm text-muted-foreground mt-1">{app.job}</p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <div className="text-right">
              <p className="text-sm font-medium">Match: {app.matchScore}%</p>
              <p className="text-xs text-muted-foreground">
                {app.appliedDays === 0
                  ? "Today"
                  : `${app.appliedDays}d ago`}
              </p>
            </div>
            <Badge
              className={`${statusColors[app.status].bg} ${statusColors[app.status].text} capitalize`}
            >
              {app.status}
            </Badge>
          </div>
        </div>
      ))}
    </div>
  );
}

