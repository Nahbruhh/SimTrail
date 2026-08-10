from __future__ import annotations

from datetime import datetime, timedelta

from .models import Run


def demo_runs() -> list[Run]:
    now = datetime.now().replace(second=0, microsecond=0)
    common = {
        "Geometry": "BRKT-042 rev C", "Material": "Al 7075-T6",
        "Load / Fx": "12.0 kN", "Load / Fy": "-4.0 kN", "Constraint": "Fixed support",
        "Element order": "Quadratic", "Solver controls": "Program controlled",
    }
    variants = [
        ("Baseline · rev C", 8, "Bonded", "2.0 mm", "1.18 M", "286 MPa", "0.82 mm", 1.76, "Approved reference", 7),
        ("Rib thickness 10 mm", 10, "Bonded", "2.0 mm", "1.24 M", "249 MPa", "0.69 mm", 2.02, "Candidate", 6),
        ("Frictional contact", 10, "Frictional · μ 0.20", "2.0 mm", "1.31 M", "271 MPa", "0.75 mm", 1.85, "Review", 5),
        ("Mesh refinement", 10, "Frictional · μ 0.20", "1.2 mm", "2.08 M", "279 MPa", "0.73 mm", 1.79, "Solved", 3),
        ("Load case LC-07", 10, "Frictional · μ 0.20", "1.2 mm", "2.08 M", "318 MPa", "0.91 mm", 1.57, "Needs review", 1),
    ]
    runs: list[Run] = []
    for index, (name, rib, contact, mesh, nodes, stress, deformation, sf, status, days) in enumerate(variants):
        inputs = dict(common)
        inputs.update({"Rib thickness": f"{rib} mm", "Contact / bracket-pin": contact,
                       "Global mesh size": mesh, "Mesh nodes": nodes})
        if index == 4:
            inputs["Load / Fx"] = "14.5 kN"
        runs.append(Run(
            name=name, project="A320 Actuator Bracket", analyst="M. Nguyen" if index < 3 else "D. Tran",
            created_at=now - timedelta(days=days, hours=index), status=status,
            notes="Captured automatically after solve. " + ("Design review candidate." if index == 1 else ""),
            source_path=rf"D:\FEA\Actuator_Bracket\run_{index + 1:02d}.wbpj", inputs=inputs,
            results={"Max equivalent stress": stress, "Max total deformation": deformation,
                     "Minimum safety factor": sf, "Solve time": f"{31 + index * 7} min"},
        ))
    runs.extend([
        Run("Thermal preload · 80°C", "Valve Housing", "A. Pham", now - timedelta(days=2),
            inputs={"Geometry": "VH-108 rev B", "Material": "316L", "Temperature": "80 °C",
                    "Global mesh size": "2.5 mm", "Mesh nodes": "842 k"},
            results={"Max equivalent stress": "164 MPa", "Max total deformation": "0.31 mm",
                     "Minimum safety factor": 1.92, "Solve time": "18 min"}),
        Run("Proof pressure · 1.5×", "Valve Housing", "A. Pham", now - timedelta(hours=8),
            status="Solved", inputs={"Geometry": "VH-108 rev B", "Material": "316L",
                    "Pressure": "18 bar", "Global mesh size": "2.5 mm", "Mesh nodes": "861 k"},
            results={"Max equivalent stress": "191 MPa", "Max total deformation": "0.38 mm",
                     "Minimum safety factor": 1.64, "Solve time": "22 min"}),
    ])
    return runs

