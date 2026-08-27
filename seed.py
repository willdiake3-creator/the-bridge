"""
Populates fields_of_study / universities / programs / scholarships from
the same taxonomy used in the frontend's programs.html, so the API and
the prototype UI agree with each other once you point the frontend at
this backend instead of its hardcoded JS array.

Run after applying schema.sql:
    python -m scripts.seed
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app import models

REGION = {
    "USA": "North America", "Canada": "North America",
    "Germany": "Europe", "France": "Europe", "Netherlands": "Europe", "Italy": "Europe",
    "Spain": "Europe", "UK": "Europe", "Switzerland": "Europe", "Sweden": "Europe",
    "Denmark": "Europe", "Finland": "Europe", "Norway": "Europe",
    "Estonia": "Eastern Europe", "Poland": "Eastern Europe", "Czechia": "Eastern Europe", "Hungary": "Eastern Europe",
    "Japan": "Asia", "South Korea": "Asia", "China": "Asia", "Singapore": "Asia",
}

DEGREE_MAP = {"Undergraduate": "undergraduate", "Master": "master", "PhD": "phd",
              "Master (LLM)": "master", "Doctorate": "phd"}
FEE_MAP = {"fee-0": "zero_fee", "fee-waiver": "fee_waiver_available", "fee-req": "fee_required"}
DEFAULT_FEE_CENTS = {"zero_fee": 0, "fee_waiver_available": 7500, "fee_required": 9500}

# id, category, name, blurb, [[uni,country,level,fee]], scholarship
FIELDS = [
    ("ai-ml", "Technology & Computing", "Artificial Intelligence & Machine Learning",
     "Deep learning, neural networks, and generative AI systems.",
     [("Carnegie Mellon University", "USA", "Master", "fee-req"),
      ("ETH Zürich", "Switzerland", "Master", "fee-req"),
      ("TU Munich", "Germany", "PhD", "fee-0")],
     {"name": "DAAD AI & Data Science Scholarships", "provider": "DAAD",
      "covers": "Merit-based, German public MSc/PhD tracks"}),
    ("data-science", "Technology & Computing", "Data Science & Big Data Analytics",
     "Converts massive data sets into business intelligence.",
     [("University of Michigan", "USA", "Master", "fee-req"),
      ("TU Delft", "Netherlands", "Master", "fee-req")],
     {"name": "Holland Scholarship", "provider": "Nuffic", "covers": "Non-EU students, NL public universities"}),
    ("cybersecurity", "Technology & Computing", "Cybersecurity & Network Defense",
     "Securing enterprise systems, networks, and cloud infrastructure.",
     [("Georgia Institute of Technology", "USA", "Master", "fee-req"),
      ("Tallinn University of Technology", "Estonia", "Master", "fee-waiver")],
     {"name": "Fulbright Foreign Student Program", "provider": "Fulbright", "covers": "US-bound, need + merit"}),
    ("software-eng", "Technology & Computing", "Software Engineering",
     "Full-stack development, software architecture, system scalability.",
     [("University of Waterloo", "Canada", "Master", "fee-req"),
      ("KTH Royal Institute of Technology", "Sweden", "Master", "fee-req")],
     {"name": "Swedish Institute Scholarships", "provider": "Swedish Institute", "covers": "Full tuition + stipend"}),
    ("cloud-devops", "Technology & Computing", "Cloud Computing & DevOps",
     "Modern cloud architecture (AWS, Azure) and CI/CD pipelines.",
     [("Arizona State University", "USA", "Master", "fee-req"),
      ("RWTH Aachen University", "Germany", "Master", "fee-0")],
     {"name": "DAAD STIBET Grants", "provider": "DAAD", "covers": "Enrolled-student support"}),
    ("comp-sci", "Technology & Computing", "Computer Science",
     "Algorithm design, systems programming, computing theory.",
     [("MIT", "USA", "Master", "fee-req"), ("TU Munich", "Germany", "Master", "fee-0")],
     {"name": "Erasmus Mundus Joint Masters", "provider": "European Commission", "covers": "Full scholarship"}),
    ("ux-hci", "Technology & Computing", "UX/UI Design & Human-Computer Interaction",
     "Cognitive psychology meets digital product design.",
     [("Carnegie Mellon HCII", "USA", "Master", "fee-req"), ("Aalto University", "Finland", "Master", "fee-waiver")],
     {"name": "Aalto University Scholarship", "provider": "Aalto University", "covers": "Tuition waiver"}),
    ("robotics", "Technology & Computing", "Robotics & Autonomous Systems",
     "Hardware, computer vision, and AI control systems.",
     [("ETH Zürich", "Switzerland", "Master", "fee-req"), ("University of Tokyo", "Japan", "Master", "fee-waiver")],
     {"name": "MEXT Scholarship", "provider": "Japanese Government", "covers": "Full funding"}),
    ("mis", "Technology & Computing", "Management Information Systems",
     "Bridges IT operations, software implementation, and strategy.",
     [("University of Texas at Austin", "USA", "Master", "fee-req"), ("Copenhagen Business School", "Denmark", "Master", "fee-req")],
     {"name": "Danish Government Scholarship", "provider": "Denmark", "covers": "Tuition waiver + stipend"}),
    ("fintech", "Technology & Computing", "FinTech & Digital Currency Systems",
     "Automated trading engines, blockchain, digital finance.",
     [("Imperial College London", "UK", "Master", "fee-req"), ("National University of Singapore", "Singapore", "Master", "fee-req")],
     {"name": "Chevening Scholarship", "provider": "UK Government", "covers": "Fully funded"}),

    ("nursing", "Healthcare & Life Sciences", "Nursing (BSN / MSN)",
     "Consistently among the highest-employment healthcare degrees.",
     [("University of Pennsylvania", "USA", "Master", "fee-req"), ("King's College London", "UK", "Master", "fee-req")],
     {"name": "Commonwealth Scholarship", "provider": "UK Government", "covers": "Commonwealth-country applicants"}),
    ("health-informatics", "Healthcare & Life Sciences", "Health Informatics & Digital Health",
     "Medical data, EHR systems, and telemetry.",
     [("Indiana University", "USA", "Master", "fee-req"), ("Karolinska Institutet", "Sweden", "Master", "fee-req")],
     {"name": "Swedish Institute Scholarships", "provider": "Swedish Institute", "covers": "Full tuition + stipend"}),
    ("phys-therapy", "Healthcare & Life Sciences", "Physical Therapy & Rehabilitation",
     "High demand, driven by aging global demographics.",
     [("University of Southern California", "USA", "Doctorate", "fee-req"), ("University of Toronto", "Canada", "Master", "fee-req")],
     {"name": "Vanier Canada Graduate Scholarships", "provider": "Government of Canada", "covers": "Doctoral level"}),
    ("health-admin", "Healthcare & Life Sciences", "Healthcare Administration",
     "Prepares managers for hospitals and health systems.",
     [("Cornell University", "USA", "Master", "fee-req"), ("University of Manchester", "UK", "Master", "fee-req")],
     {"name": "Fulbright Foreign Student Program", "provider": "Fulbright", "covers": "US-bound, need + merit"}),
    ("biomed-sci", "Healthcare & Life Sciences", "Biomedical Sciences",
     "Research in genetic therapies, immunology, oncology.",
     [("Johns Hopkins University", "USA", "PhD", "fee-req"), ("Karolinska Institutet", "Sweden", "Master", "fee-req")],
     {"name": "Karolinska Institutet Global Scholarship", "provider": "Karolinska Institutet", "covers": "Partial tuition"}),
    ("pharmacy", "Healthcare & Life Sciences", "Pharmacy & Pharmaceutical Chemistry",
     "Drug discovery, clinical trials, pharmacology.",
     [("University of Toronto", "Canada", "Master", "fee-req"), ("University of Copenhagen", "Denmark", "Master", "fee-0")],
     {"name": "Danish Government Scholarship", "provider": "Denmark", "covers": "Tuition waiver + stipend"}),
    ("public-health", "Healthcare & Life Sciences", "Public Health (MPH)",
     "Epidemiology, biostatistics, global health policy.",
     [("Harvard T.H. Chan School", "USA", "Master", "fee-req"), ("LSHTM", "UK", "Master", "fee-req")],
     {"name": "Commonwealth Scholarship", "provider": "UK Government", "covers": "Commonwealth-country applicants"}),
    ("med-lab-sci", "Healthcare & Life Sciences", "Medical Laboratory Science",
     "Diagnostic training for clinical labs and pathology.",
     [("University of Alberta", "Canada", "Master", "fee-req"), ("Charité – Universitätsmedizin Berlin", "Germany", "Master", "fee-0")],
     {"name": "DAAD STIBET Grants", "provider": "DAAD", "covers": "Enrolled-student support"}),
    ("occ-therapy", "Healthcare & Life Sciences", "Occupational Therapy",
     "Assists patient recovery and functional independence.",
     [("Boston University", "USA", "Master", "fee-req"), ("McGill University", "Canada", "Master", "fee-req")],
     {"name": "Vanier Canada Graduate Scholarships", "provider": "Government of Canada", "covers": "Doctoral level"}),
    ("clinical-psych", "Healthcare & Life Sciences", "Clinical Psychology & Behavioral Health",
     "Rising global demand for mental health practitioners.",
     [("Columbia University", "USA", "Master", "fee-req"), ("Utrecht University", "Netherlands", "Master", "fee-req")],
     {"name": "Holland Scholarship", "provider": "Nuffic", "covers": "Non-EU students, NL public universities"}),

    ("electrical-eng", "Engineering & Hardware", "Electrical Engineering",
     "Power systems, microelectronics, semiconductor manufacturing.",
     [("Stanford University", "USA", "Master", "fee-req"), ("TU Munich", "Germany", "Master", "fee-0")],
     {"name": "DAAD EPOS Scholarships", "provider": "DAAD", "covers": "Development-related engineering programs"}),
    ("mech-eng", "Engineering & Hardware", "Mechanical Engineering",
     "Manufacturing, automotive design, robotics, HVAC.",
     [("University of Michigan", "USA", "Master", "fee-req"), ("RWTH Aachen University", "Germany", "Master", "fee-0")],
     {"name": "DAAD STIBET Grants", "provider": "DAAD", "covers": "Enrolled-student support"}),
    ("civil-eng", "Engineering & Hardware", "Civil & Structural Engineering",
     "Global infrastructure, transport, and building design.",
     [("UC Berkeley", "USA", "Master", "fee-req"), ("TU Delft", "Netherlands", "Master", "fee-req")],
     {"name": "Holland Scholarship", "provider": "Nuffic", "covers": "Non-EU students, NL public universities"}),
    ("aerospace", "Engineering & Hardware", "Aerospace & Aeronautical Engineering",
     "Commercial aviation, defense systems, space technology.",
     [("Georgia Institute of Technology", "USA", "Master", "fee-req"), ("TU Delft", "Netherlands", "Master", "fee-req")],
     {"name": "Holland Scholarship", "provider": "Nuffic", "covers": "Non-EU students, NL public universities"}),
    ("biomed-eng", "Engineering & Hardware", "Biomedical Engineering",
     "Medical devices, prosthetics, artificial organs.",
     [("Johns Hopkins University", "USA", "Master", "fee-req"), ("Imperial College London", "UK", "Master", "fee-req")],
     {"name": "Chevening Scholarship", "provider": "UK Government", "covers": "Fully funded"}),
    ("chem-eng", "Engineering & Hardware", "Chemical Engineering",
     "Pharmaceuticals, advanced materials, industrial energy.",
     [("MIT", "USA", "Master", "fee-req"), ("ETH Zürich", "Switzerland", "Master", "fee-req")],
     {"name": "ETH Zürich Excellence Scholarship", "provider": "ETH Zürich", "covers": "Merit-based"}),
    ("industrial-eng", "Engineering & Hardware", "Industrial & Systems Engineering",
     "Supply chains, manufacturing, operational efficiency.",
     [("Georgia Institute of Technology", "USA", "Master", "fee-req"), ("KAIST", "South Korea", "Master", "fee-waiver")],
     {"name": "KGSP — Korean Government Scholarship", "provider": "South Korea", "covers": "Full funding"}),
    ("mechatronics", "Engineering & Hardware", "Mechatronics Engineering",
     "Blends mechanical design, electronics, and microcontrollers.",
     [("TU Munich", "Germany", "Master", "fee-0"), ("KAIST", "South Korea", "Master", "fee-waiver")],
     {"name": "KGSP — Korean Government Scholarship", "provider": "South Korea", "covers": "Full funding"}),
    ("computer-eng", "Engineering & Hardware", "Computer Engineering",
     "Hardware architecture with low-level software and firmware.",
     [("Carnegie Mellon University", "USA", "Master", "fee-req"), ("National University of Singapore", "Singapore", "Master", "fee-req")],
     {"name": "NUS Research Scholarship", "provider": "NUS", "covers": "Full tuition + stipend"}),

    ("biz-analytics", "Business, Finance & Analytics", "Business Analytics",
     "Quantitative modeling for corporate decision-making.",
     [("University of Texas at Austin", "USA", "Master", "fee-req"), ("HEC Paris", "France", "Master", "fee-req")],
     {"name": "Eiffel Excellence Scholarship", "provider": "French Government", "covers": "Top-ranked applicants"}),
    ("finance-inv", "Business, Finance & Analytics", "Finance & Investment Management",
     "Corporate capital, asset management, investment banking.",
     [("London Business School", "UK", "Master", "fee-req"), ("Bocconi University", "Italy", "Master", "fee-req")],
     {"name": "Bocconi Merit Scholarship", "provider": "Bocconi University", "covers": "Tuition reduction"}),
    ("supply-chain", "Business, Finance & Analytics", "Supply Chain Management & Global Logistics",
     "International trade, warehouse automation, shipping.",
     [("MIT", "USA", "Master", "fee-req"), ("Erasmus University Rotterdam", "Netherlands", "Master", "fee-req")],
     {"name": "Holland Scholarship", "provider": "Nuffic", "covers": "Non-EU students, NL public universities"}),
    ("accounting", "Business, Finance & Analytics", "Accounting & Auditing",
     "Corporate governance and financial compliance.",
     [("University of Illinois Urbana-Champaign", "USA", "Master", "fee-req"), ("University of Amsterdam", "Netherlands", "Master", "fee-req")],
     {"name": "Amsterdam Merit Scholarship", "provider": "University of Amsterdam", "covers": "Non-EEA students"}),
    ("actuarial", "Business, Finance & Analytics", "Actuarial Science",
     "Advanced statistics and probability to model risk.",
     [("University of Waterloo", "Canada", "Undergraduate", "fee-req"), ("Heriot-Watt University", "UK", "Master", "fee-req")],
     {"name": "Chevening Scholarship", "provider": "UK Government", "covers": "Fully funded"}),
    ("digital-marketing", "Business, Finance & Analytics", "Digital Marketing & Growth Analytics",
     "SEO, performance marketing, conversion optimization.",
     [("Northwestern University (Medill)", "USA", "Master", "fee-req"), ("IE University", "Spain", "Master", "fee-req")],
     {"name": "IE Excellence Scholarship", "provider": "IE University", "covers": "Merit-based tuition reduction"}),
    ("intl-business", "Business, Finance & Analytics", "International Business Management",
     "Cross-border operations and global strategy.",
     [("Copenhagen Business School", "Denmark", "Master", "fee-req"), ("ESADE Business School", "Spain", "Master", "fee-req")],
     {"name": "Danish Government Scholarship", "provider": "Denmark", "covers": "Tuition waiver + stipend"}),
    ("project-mgmt", "Business, Finance & Analytics", "Project Management",
     "Leadership methodology across tech, construction, corporate.",
     [("Boston University", "USA", "Master", "fee-req"), ("University of Warwick", "UK", "Master", "fee-req")],
     {"name": "Chevening Scholarship", "provider": "UK Government", "covers": "Fully funded"}),
    ("fin-economics", "Business, Finance & Analytics", "Financial Economics",
     "Econometric modeling with micro/macro policy analysis.",
     [("London School of Economics", "UK", "Master", "fee-req"), ("University of Mannheim", "Germany", "Master", "fee-0")],
     {"name": "DAAD STIBET Grants", "provider": "DAAD", "covers": "Enrolled-student support"}),

    ("renewable-energy", "Sustainability & Energy Transition", "Renewable Energy Engineering",
     "Solar, wind, battery storage, smart-grid development.",
     [("TU Delft", "Netherlands", "Master", "fee-req"), ("NTNU", "Norway", "Master", "fee-0")],
     {"name": "Holland Scholarship", "provider": "Nuffic", "covers": "Non-EU students, NL public universities"}),
    ("env-science", "Sustainability & Energy Transition", "Environmental Science & Sustainability Management",
     "Corporate compliance and climate advisory.",
     [("Yale School of the Environment", "USA", "Master", "fee-req"), ("Lund University", "Sweden", "Master", "fee-req")],
     {"name": "Swedish Institute Scholarships", "provider": "Swedish Institute", "covers": "Full tuition + stipend"}),
    ("climate-policy", "Sustainability & Energy Transition", "Climate Policy & Environmental Economics",
     "Carbon credits, regulation, environmental law.",
     [("London School of Economics", "UK", "Master", "fee-req"), ("Sciences Po", "France", "Master", "fee-req")],
     {"name": "Eiffel Excellence Scholarship", "provider": "French Government", "covers": "Top-ranked applicants"}),
    ("agritech", "Sustainability & Energy Transition", "Agricultural Science & AgriTech",
     "Automated farming, crop genetics, food security.",
     [("Wageningen University", "Netherlands", "Master", "fee-req"), ("UC Davis", "USA", "Master", "fee-req")],
     {"name": "Holland Scholarship", "provider": "Nuffic", "covers": "Non-EU students, NL public universities"}),
    ("sustainable-arch", "Sustainability & Energy Transition", "Sustainable Architecture & Green Design",
     "Energy-efficient, net-zero building systems.",
     [("TU Delft", "Netherlands", "Master", "fee-req"), ("KTH Royal Institute of Technology", "Sweden", "Master", "fee-req")],
     {"name": "Swedish Institute Scholarships", "provider": "Swedish Institute", "covers": "Full tuition + stipend"}),
    ("water-resources", "Sustainability & Energy Transition", "Water Resources & Hydrological Engineering",
     "Climate resilience, water treatment, infrastructure.",
     [("TU Delft", "Netherlands", "Master", "fee-req"), ("IHE Delft Institute for Water Education", "Netherlands", "Master", "fee-waiver")],
     {"name": "Orange Knowledge Programme", "provider": "Nuffic", "covers": "Full scholarship, developing countries"}),

    ("game-dev", "Media, Design & Interdisciplinary Studies", "Game Development & Interactive Media",
     "3D rendering engines, physics, narrative design.",
     [("University of Southern California", "USA", "Master", "fee-req"), ("Breda University of Applied Sciences", "Netherlands", "Master", "fee-req")],
     {"name": "Holland Scholarship", "provider": "Nuffic", "covers": "Non-EU students, NL public universities"}),
    ("ip-law", "Media, Design & Interdisciplinary Studies", "Intellectual Property & Technology Law",
     "Patent law, AI governance, digital copyright.",
     [("George Washington University", "USA", "Master (LLM)", "fee-req"), ("MIPLC Munich", "Germany", "Master (LLM)", "fee-req")],
     {"name": "DAAD STIBET Grants", "provider": "DAAD", "covers": "Enrolled-student support"}),
    ("digital-comms", "Media, Design & Interdisciplinary Studies", "Digital Communications & Media Studies",
     "Content strategy, PR, digital brand building.",
     [("Columbia Journalism School", "USA", "Master", "fee-req"), ("University of Amsterdam", "Netherlands", "Master", "fee-req")],
     {"name": "Amsterdam Merit Scholarship", "provider": "University of Amsterdam", "covers": "Non-EEA students"}),
    ("instr-design", "Media, Design & Interdisciplinary Studies", "Instructional Design & Educational Technology",
     "Corporate e-learning and curriculum models.",
     [("Harvard Graduate School of Education", "USA", "Master", "fee-req"), ("UCL Institute of Education", "UK", "Master", "fee-req")],
     {"name": "Chevening Scholarship", "provider": "UK Government", "covers": "Fully funded"}),
    ("urban-planning", "Media, Design & Interdisciplinary Studies", "Urban Planning & Smart Cities",
     "GIS mapping, transit planning, municipal development.",
     [("MIT", "USA", "Master", "fee-req"), ("TU Delft", "Netherlands", "Master", "fee-req")],
     {"name": "Holland Scholarship", "provider": "Nuffic", "covers": "Non-EU students, NL public universities"}),
    ("bioethics", "Media, Design & Interdisciplinary Studies", "Bioethics & Medical Humanities",
     "Legal and ethical frameworks in healthcare research.",
     [("University of Pennsylvania", "USA", "Master", "fee-req"), ("King's College London", "UK", "Master", "fee-req")],
     {"name": "Chevening Scholarship", "provider": "UK Government", "covers": "Fully funded"}),
]


def run():
    db = SessionLocal()
    try:
        university_cache: dict[str, models.University] = {}

        for slug, category, name, blurb, unis, scholarship in FIELDS:
            field = db.query(models.FieldOfStudy).filter_by(slug=slug).first()
            if field is None:
                field = models.FieldOfStudy(slug=slug, category=category, name=name, description=blurb)
                db.add(field)
                db.flush()

            sch = db.query(models.Scholarship).filter_by(name=scholarship["name"]).first()
            if sch is None:
                sch = models.Scholarship(
                    name=scholarship["name"], provider=scholarship.get("provider"),
                    covers=scholarship.get("covers"),
                )
                db.add(sch)
                db.flush()

            for uni_name, country, level, fee_key in unis:
                cache_key = f"{uni_name}|{country}"
                uni = university_cache.get(cache_key)
                if uni is None:
                    uni = db.query(models.University).filter_by(name=uni_name, country=country).first()
                    if uni is None:
                        uni = models.University(name=uni_name, country=country, region=REGION[country])
                        db.add(uni)
                        db.flush()
                    university_cache[cache_key] = uni

                fee_status = FEE_MAP[fee_key]
                program = models.Program(
                    university_id=uni.id,
                    field_of_study_id=field.id,
                    name=f"{DEGREE_MAP[level].capitalize()} in {name}",
                    degree_level=DEGREE_MAP[level],
                    fee_status=fee_status,
                    application_fee_cents=DEFAULT_FEE_CENTS[fee_status],
                    currency="USD",
                )
                db.add(program)
                db.flush()
                db.add(models.ProgramScholarship(program_id=program.id, scholarship_id=sch.id))

        db.commit()
        print(f"Seeded {len(FIELDS)} fields across {len(university_cache)} universities.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
