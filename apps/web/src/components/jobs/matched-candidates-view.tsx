"use client";

import { useState } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Brain, Star, TrendingUp, Mail, Phone, MapPin } from "lucide-react";

interface MatchedCandidatesViewProps {
  jobId: string;
}

// Mock data - in production, this would be fetched from API
const mockMatches = [
  {
    id: "1",
    name: "Alice Johnson",
    email: "alice@example.com",
    phone: "(555) 123-4567",
    location: "San Francisco, CA",
    matchScore: 94,
    aiRationale: "Exceptional match with 6+ years of relevant experience. Strong Python and FastAPI expertise. All required skills present with advanced proficiency.",
    skills: [
      { name: "Python", match: true, level: "Expert" },
      { name: "FastAPI", match: true, level: "Advanced" },
      { name: "PostgreSQL", match: true, level: "Advanced" },
      { name: "Docker", match: true, level: "Intermediate" },
      { name: "Kubernetes", match: true, level: "Intermediate" },
    ],
    experience: 6,
    currentRole: "Senior Software Engineer at TechCorp",
    education: "B.S. Computer Science, Stanford University",
    status: "available",
  },
  {
    id: "2",
    name: "David Chen",
    email: "david@example.com",
    phone: "(555) 234-5678",
    location: "Palo Alto, CA",
    matchScore: 89,
    aiRationale: "Strong technical background with 5 years experience. Excellent Python skills and cloud experience. Minor gaps in Kubernetes expertise but quick learner profile.",
    skills: [
      { name: "Python", match: true, level: "Advanced" },
      { name: "FastAPI", match: true, level: "Intermediate" },
      { name: "PostgreSQL", match: true, level: "Intermediate" },
      { name: "Docker", match: true, level: "Advanced" },
    ],
    experience: 5,
    currentRole: "Software Engineer at CloudScale",
    education: "M.S. Computer Science, UC Berkeley",
    status: "passive",
  },
  {
    id: "3",
    name: "Sarah Martinez",
    email: "sarah@example.com",
    phone: "(555) 345-6789",
    location: "San Jose, CA",
    matchScore: 86,
    aiRationale: "Solid candidate with relevant backend experience. Strong database skills and microservices architecture experience. Would benefit from more FastAPI exposure.",
    skills: [
      { name: "Python", match: true, level: "Advanced" },
      { name: "Django", match: false, level: "Expert" },
      { name: "PostgreSQL", match: true, level: "Expert" },
      { name: "Redis", match: false, level: "Advanced" },
    ],
    experience: 4,
    currentRole: "Backend Engineer at DataFlow",
    education: "B.S. Software Engineering, San Jose State",
    status: "available",
  },
];

export function MatchedCandidatesView({ jobId }: MatchedCandidatesViewProps) {
  const [loading, setLoading] = useState(false);

  const handleMatchCandidates = async () => {
    setLoading(true);
    // TODO: Call API to get AI-matched candidates
    setTimeout(() => setLoading(false), 2000);
  };

  return (
    <div className="space-y-4">
      {/* AI Matching Banner */}
      <Card className="border-primary/50 bg-primary/5">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-full bg-primary/10">
                <Brain className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold">AI-Powered Semantic Matching</h3>
                <p className="text-sm text-muted-foreground">
                  Using vector embeddings and GPT-4o to find the best candidates
                </p>
              </div>
            </div>
            <Button onClick={handleMatchCandidates} disabled={loading}>
              {loading ? "Matching..." : "Refresh Matches"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Matched Candidates */}
      <div className="space-y-4">
        {mockMatches.map((candidate, index) => (
          <Card
            key={candidate.id}
            className="hover:shadow-lg transition-all cursor-pointer"
          >
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <div className="relative">
                    <Avatar className="h-12 w-12">
                      <AvatarFallback className="bg-primary text-primary-foreground">
                        {candidate.name
                          .split(" ")
                          .map((n) => n[0])
                          .join("")}
                      </AvatarFallback>
                    </Avatar>
                    {index === 0 && (
                      <div className="absolute -top-1 -right-1">
                        <Star className="h-5 w-5 text-brand-gold fill-brand-gold" />
                      </div>
                    )}
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-semibold">{candidate.name}</h3>
                      <Badge
                        variant={
                          candidate.status === "available" ? "default" : "outline"
                        }
                      >
                        {candidate.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {candidate.currentRole}
                    </p>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Mail className="h-3 w-3" />
                        {candidate.email}
                      </span>
                      <span className="flex items-center gap-1">
                        <Phone className="h-3 w-3" />
                        {candidate.phone}
                      </span>
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" />
                        {candidate.location}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Match Score */}
                <div className="text-right space-y-2">
                  <div className="space-y-1">
                    <div className="text-3xl font-bold text-primary">
                      {candidate.matchScore}%
                    </div>
                    <p className="text-xs text-muted-foreground">Match Score</p>
                  </div>
                  <Progress value={candidate.matchScore} className="w-24" />
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* AI Rationale */}
              <div className="p-4 rounded-lg bg-muted/50 border border-primary/20">
                <div className="flex items-start gap-2">
                  <Brain className="h-5 w-5 text-primary mt-0.5" />
                  <div>
                    <p className="text-sm font-medium mb-1">AI Analysis</p>
                    <p className="text-sm text-muted-foreground">
                      {candidate.aiRationale}
                    </p>
                  </div>
                </div>
              </div>

              {/* Skills Match */}
              <div>
                <p className="text-sm font-medium mb-2">Skills Match</p>
                <div className="flex flex-wrap gap-2">
                  {candidate.skills.map((skill) => (
                    <Badge
                      key={skill.name}
                      variant={skill.match ? "default" : "outline"}
                      className={skill.match ? "bg-brand-teal text-white" : ""}
                    >
                      {skill.name} ({skill.level})
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Quick Stats */}
              <div className="flex items-center gap-6 text-sm text-muted-foreground">
                <span>{candidate.experience} years experience</span>
                <span>•</span>
                <span>{candidate.education}</span>
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-2">
                <Button size="sm" className="flex-1">
                  View Full Profile
                </Button>
                <Button size="sm" variant="outline" className="flex-1">
                  Schedule Interview
                </Button>
                <Button size="sm" variant="outline">
                  <Mail className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Load More */}
      <div className="text-center">
        <Button variant="outline" className="w-full md:w-auto">
          Load More Candidates
        </Button>
      </div>
    </div>
  );
}
