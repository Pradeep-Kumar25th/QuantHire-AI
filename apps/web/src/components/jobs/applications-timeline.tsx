"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Clock, CheckCircle, XCircle, AlertCircle } from "lucide-react";

interface ApplicationsTimelineProps {
  jobId: string;
}

const timelineData = [
  {
    id: "1",
    candidate: "Alice Johnson",
    action: "Application submitted",
    timestamp: "2 hours ago",
    status: "screening",
    icon: CheckCircle,
    color: "text-brand-teal border-brand-teal",
  },
  {
    id: "2",
    candidate: "David Chen",
    action: "Interview completed",
    timestamp: "5 hours ago",
    status: "interviewing",
    icon: CheckCircle,
    color: "text-brand-gold border-brand-gold",
  },
  {
    id: "3",
    candidate: "Sarah Martinez",
    action: "Assessment passed",
    timestamp: "1 day ago",
    status: "assessment",
    icon: CheckCircle,
    color: "text-brand-gray border-brand-gray",
  },
  {
    id: "4",
    candidate: "Michael Brown",
    action: "Application rejected",
    timestamp: "2 days ago",
    status: "rejected",
    icon: XCircle,
    color: "text-brand-red border-brand-red",
  },
  {
    id: "5",
    candidate: "Emma Wilson",
    action: "Screening in progress",
    timestamp: "3 days ago",
    status: "screening",
    icon: Clock,
    color: "text-brand-gold border-brand-gold",
  },
];

export function ApplicationsTimeline({ jobId }: ApplicationsTimelineProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="space-y-6">
          {timelineData.map((item, index) => (
            <div key={item.id} className="flex gap-4">
              {/* Timeline line */}
              <div className="flex flex-col items-center">
                <div className={`p-2 rounded-full bg-background border-2 ${item.color}`}>
                  <item.icon className="h-4 w-4" />
                </div>
                {index < timelineData.length - 1 && (
                  <div className="w-0.5 h-full bg-border mt-2" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 pb-6">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Avatar className="h-8 w-8">
                        <AvatarFallback className="text-xs">
                          {item.candidate
                            .split(" ")
                            .map((n) => n[0])
                            .join("")}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="font-medium">{item.candidate}</p>
                        <p className="text-sm text-muted-foreground">
                          {item.action}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-muted-foreground">{item.timestamp}</p>
                    <Badge variant="outline" className="mt-1 capitalize">
                      {item.status}
                    </Badge>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

