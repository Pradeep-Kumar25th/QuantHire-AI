"use client";

const jobs = [
  { title: "Senior Software Engineer", applications: 45, filled: 1, total: 2 },
  { title: "Frontend Developer", applications: 38, filled: 0, total: 1 },
  { title: "Product Manager", applications: 32, filled: 0, total: 1 },
  { title: "Data Scientist", applications: 28, filled: 1, total: 3 },
  { title: "UX Designer", applications: 24, filled: 0, total: 2 },
];

export function TopJobs() {
  return (
    <div className="space-y-4">
      {jobs.map((job, index) => (
        <div key={index} className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium leading-none">{job.title}</p>
            <p className="text-sm text-muted-foreground">
              {job.applications} applications
            </p>
          </div>
          <div className="text-sm text-muted-foreground">
            {job.filled}/{job.total} filled
          </div>
        </div>
      ))}
    </div>
  );
}

