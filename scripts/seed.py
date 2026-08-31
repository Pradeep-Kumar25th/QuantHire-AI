#!/usr/bin/env python
"""Seed database with sample data for development."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import (
    Application,
    ApplicationStatus,
    Candidate,
    Job,
    JobStatus,
    User,
    UserRole,
)


async def seed_database():
    """Seed database with sample data."""
    print("🌱 Seeding database...")

    # Create async engine
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create users
        admin = User(
            id=uuid4(),
            email="admin@quanthire.ai",
            name="Admin User",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )

        recruiter = User(
            id=uuid4(),
            email="recruiter@quanthire.ai",
            name="Jane Recruiter",
            role=UserRole.RECRUITER,
            is_active=True,
            is_verified=True,
        )

        hiring_manager = User(
            id=uuid4(),
            email="manager@quanthire.ai",
            name="Bob Manager",
            role=UserRole.HIRING_MANAGER,
            is_active=True,
            is_verified=True,
        )

        session.add_all([admin, recruiter, hiring_manager])
        await session.flush()

        print(f"✓ Created {3} users")

        # Create jobs
        jobs_data = [
            {
                "title": "Senior Software Engineer",
                "level": "Senior",
                "department": "Engineering",
                "location": "San Francisco, CA",
                "remote_allowed": True,
                "description": "We're looking for a senior engineer to lead our backend team.",
                "spec_json": {
                    "skills": [
                        {"name": "Python", "required": True, "level": "Advanced"},
                        {"name": "FastAPI", "required": True, "level": "Intermediate"},
                        {"name": "PostgreSQL", "required": True, "level": "Intermediate"},
                        {"name": "Docker", "required": False, "level": "Beginner"},
                    ],
                    "responsibilities": [
                        "Lead backend development",
                        "Mentor junior engineers",
                        "Design scalable systems",
                    ],
                },
                "status": JobStatus.OPEN,
            },
            {
                "title": "Frontend Developer",
                "level": "Mid",
                "department": "Engineering",
                "location": "New York, NY",
                "remote_allowed": True,
                "description": "Join our frontend team building amazing user experiences.",
                "spec_json": {
                    "skills": [
                        {"name": "React", "required": True, "level": "Advanced"},
                        {"name": "TypeScript", "required": True, "level": "Intermediate"},
                        {"name": "TailwindCSS", "required": False, "level": "Beginner"},
                    ],
                    "responsibilities": [
                        "Build responsive UIs",
                        "Collaborate with designers",
                        "Optimize performance",
                    ],
                },
                "status": JobStatus.OPEN,
            },
            {
                "title": "Product Manager",
                "level": "Senior",
                "department": "Product",
                "location": "Remote",
                "remote_allowed": True,
                "description": "Drive product strategy and execution.",
                "spec_json": {
                    "skills": [
                        {"name": "Product Management", "required": True, "level": "Advanced"},
                        {"name": "Agile", "required": True, "level": "Intermediate"},
                        {"name": "User Research", "required": False, "level": "Intermediate"},
                    ],
                    "responsibilities": [
                        "Define product roadmap",
                        "Work with engineering",
                        "Analyze metrics",
                    ],
                },
                "status": JobStatus.OPEN,
            },
        ]

        jobs = []
        for job_data in jobs_data:
            job = Job(
                id=uuid4(),
                created_by=recruiter.id,
                hiring_manager_id=hiring_manager.id,
                **job_data,
            )
            jobs.append(job)
            session.add(job)

        await session.flush()
        print(f"✓ Created {len(jobs)} jobs")

        # Create candidates
        candidates_data = [
            {
                "name": "Alice Johnson",
                "email": "alice@example.com",
                "phone": "(555) 123-4567",
                "location": "San Francisco, CA",
                "profile_json": {
                    "experience": [
                        {
                            "company": "TechCorp",
                            "title": "Software Engineer",
                            "start": "2020-01",
                            "end": "present",
                            "bullets": [
                                "Built microservices with Python/FastAPI",
                                "Optimized database queries, reducing latency by 40%",
                            ],
                        },
                        {
                            "company": "StartupXYZ",
                            "title": "Junior Developer",
                            "start": "2018-06",
                            "end": "2019-12",
                            "bullets": ["Developed REST APIs", "Implemented CI/CD pipeline"],
                        },
                    ],
                    "skills": [
                        {"name": "Python", "confidence": 0.95},
                        {"name": "FastAPI", "confidence": 0.90},
                        {"name": "PostgreSQL", "confidence": 0.85},
                        {"name": "Docker", "confidence": 0.80},
                    ],
                    "education": [
                        {
                            "degree": "B.S.",
                            "institution": "Stanford University",
                            "year": 2018,
                            "field": "Computer Science",
                        }
                    ],
                },
                "parsing_confidence": 0.92,
                "source": "upload",
            },
            {
                "name": "Bob Smith",
                "email": "bob@example.com",
                "phone": "(555) 234-5678",
                "location": "New York, NY",
                "profile_json": {
                    "experience": [
                        {
                            "company": "DesignCo",
                            "title": "Frontend Developer",
                            "start": "2019-03",
                            "end": "present",
                            "bullets": [
                                "Built responsive UIs with React",
                                "Improved performance by 50%",
                            ],
                        }
                    ],
                    "skills": [
                        {"name": "React", "confidence": 0.95},
                        {"name": "TypeScript", "confidence": 0.90},
                        {"name": "TailwindCSS", "confidence": 0.85},
                    ],
                    "education": [
                        {"degree": "B.A.", "institution": "NYU", "year": 2019, "field": "Design"}
                    ],
                },
                "parsing_confidence": 0.88,
                "source": "referral",
            },
            {
                "name": "Carol Davis",
                "email": "carol@example.com",
                "phone": "(555) 345-6789",
                "location": "Austin, TX",
                "profile_json": {
                    "experience": [
                        {
                            "company": "BigTech",
                            "title": "Senior Product Manager",
                            "start": "2017-01",
                            "end": "present",
                            "bullets": [
                                "Led product team of 10",
                                "Launched 5 major features",
                                "Increased revenue by 30%",
                            ],
                        }
                    ],
                    "skills": [
                        {"name": "Product Management", "confidence": 0.95},
                        {"name": "Agile", "confidence": 0.90},
                        {"name": "Analytics", "confidence": 0.85},
                    ],
                    "education": [
                        {"degree": "MBA", "institution": "Harvard", "year": 2015, "field": "Business"}
                    ],
                },
                "parsing_confidence": 0.95,
                "source": "linkedin",
            },
        ]

        candidates = []
        for candidate_data in candidates_data:
            candidate = Candidate(id=uuid4(), **candidate_data)
            candidates.append(candidate)
            session.add(candidate)

        await session.flush()
        print(f"✓ Created {len(candidates)} candidates")

        # Create applications
        applications = [
            Application(
                id=uuid4(),
                candidate_id=candidates[0].id,
                job_id=jobs[0].id,
                status=ApplicationStatus.SCREENING,
                match_score=85.5,
                applied_at=datetime.utcnow() - timedelta(days=3),
            ),
            Application(
                id=uuid4(),
                candidate_id=candidates[1].id,
                job_id=jobs[1].id,
                status=ApplicationStatus.INTERVIEWING,
                match_score=92.3,
                applied_at=datetime.utcnow() - timedelta(days=5),
            ),
            Application(
                id=uuid4(),
                candidate_id=candidates[2].id,
                job_id=jobs[2].id,
                status=ApplicationStatus.OFFER,
                match_score=88.7,
                applied_at=datetime.utcnow() - timedelta(days=10),
            ),
        ]

        for application in applications:
            session.add(application)

        await session.flush()
        print(f"✓ Created {len(applications)} applications")

        # Commit all changes
        await session.commit()

    print("✅ Database seeding completed!")
    print("\n📊 Summary:")
    print(f"  - Users: 3")
    print(f"  - Jobs: {len(jobs)}")
    print(f"  - Candidates: {len(candidates)}")
    print(f"  - Applications: {len(applications)}")
    print("\n🔑 Test credentials:")
    print("  Admin: admin@quanthire.ai")
    print("  Recruiter: recruiter@quanthire.ai")
    print("  Manager: manager@quanthire.ai")


if __name__ == "__main__":
    asyncio.run(seed_database())

