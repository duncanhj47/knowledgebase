#!/usr/bin/env python3
"""Import the content from https://sites.google.com/view/toyotadiesel/home
into the knowledge base, preserving the original links (Drive/Photos/
YouTube/Docs) rather than downloading and re-hosting anything.

Usage (from the project root, with the venv active):

    python scripts/import_site_content.py                # import everything
    python scripts/import_site_content.py --dry-run       # preview counts only, writes nothing
    python scripts/import_site_content.py --reset         # remove a previous import, then re-import

Everything this script creates is set live immediately (status=approved,
reviewed by the first admin account found) rather than sitting in the
moderation queue - this is your own already-curated content, not a
public submission. Everything is also tagged internally
(admin_notes=IMPORT_MARKER) so --reset only ever removes what this
script created, never anything a visitor submitted separately.

A handful of engine tags referenced on the source site don't exist in
the default taxonomy yet (13B, 1C-T, 2C-T, 3L, 5L) - this script
creates them automatically if missing, same pattern as seed_demo_data.py.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from webapp.extensions import db
from webapp.models import Resource, Category, EngineModel, VehicleModel, User
from webapp.services.resource_service import index_resource, ensure_search_index

IMPORT_MARKER = '__SITE_IMPORT__'

# ---------------------------------------------------------------------
# Content transcribed from the existing site. Each entry:
#   (title, url, resource_type, category_name, engine_codes, vehicle_codes)
# resource_type is 'url' for docs/manuals/sheets, 'photo' for Google
# Photos links, 'video' for YouTube.
# ---------------------------------------------------------------------

ENTRIES = [
    # --- General / social ---
    ("Duncan's IH8Mud Profile", "https://forum.ih8mud.com/members/duncanrm.74271/", "url", None, [], []),
    ("2H/12HT Facebook Group", "https://www.facebook.com/groups/2h12ht", "url", None, ["2H", "12HT"], []),

    # --- 2H: Factory manuals ---
    ("2H Repair Manual - 36048E (1985)",
     "https://drive.google.com/file/d/0B-KW6mdxQyjDY3dVa3dGcml4X2M/view?usp=drive_link&resourcekey=0-nxapG2mrSR2ThDaA0jOcsg",
     "url", "Factory Manual", ["2H"], []),
    ("2H Repair Manual Supplement - RM133E (Aug 1988)",
     "https://drive.google.com/file/d/16dx8ncHLI85LhWTlshodk-gNO3vH4MNU/view?usp=drive_link",
     "url", "Factory Manual", ["2H"], []),
    ("2H/12HT Service Training Information",
     "https://drive.google.com/file/d/1_LaTcMxWhpUWtSQPU4SpOlUjbrYkGe9d/view?usp=drive_link",
     "url", "Factory Manual", ["2H", "12HT"], []),

    # --- 2H: Trusted parts sources ---
    ("Technical Motors Sports Corner - Trusted 2H/12HT Parts Source",
     "https://technicalsportscorner.com.au/collections/2h", "url", "Parts Reference", ["2H", "12HT"], []),
    ("Terrain Tamer - Trusted 2H/12HT Parts Source",
     "https://www.terraintamer.com/", "url", "Parts Reference", ["2H", "12HT"], []),

    ("2H Gasket PDFs (cutting templates)",
     "https://drive.google.com/open?id=1G015RPkKQp9mibToBBTmi3ou702DfRSx",
     "url", "Parts Reference", ["2H"], []),

    # --- Early vs late 2H/12HT ---
    ("Early vs Late 2H Head Gaskets (Comparison)",
     "https://drive.google.com/open?id=1N7GDSgxqU7-HOMMZECi8DilbJ8QC_OtG",
     "url", "Parts Reference", ["2H"], []),
    ("Early vs Late 2H/12HT, How to Identify",
     "https://photos.app.goo.gl/g1UVCW1dFH1w5mLD9",
     "photo", "Reference Photos", ["2H", "12HT"], []),
    ("Early vs Late 2H/12HT Cam Comparison",
     "https://photos.app.goo.gl/9MJ9Mi7KvVyt4yGh8",
     "photo", "Reference Photos", ["2H", "12HT"], []),
    ("Early vs Late 2H/12HT Timing Case Comparison",
     "https://photos.app.goo.gl/kQqxxuHoDcs8JLz49",
     "photo", "Reference Photos", ["2H", "12HT"], []),
    ("Comparison of Early 2H and Late 2H/12HT Oil Cooler Covers",
     "https://photos.app.goo.gl/4AT8uFRUi21EX6FD7",
     "photo", "Reference Photos", ["2H", "12HT"], []),

    ("Engine Australia Early 2H Specification Sheet",
     "https://drive.google.com/file/d/19sV3mr4UKIU_zabtC_PDLitKsueYG1x1/view?usp=sharing",
     "url", "Factory Manual", ["2H"], []),
    ("Piston Protrusion Information from Engine Australia",
     "https://photos.app.goo.gl/X6moDL5CWCow13J89", "photo", "Reference Photos", ["2H"], []),
    ("Engine Australia 2H/12HT Casting Information",
     "https://photos.app.goo.gl/2PSYbw9FHucn86kCA", "photo", "Reference Photos", ["2H", "12HT"], []),
    ("ARP Head Studs for 2H/12HT from Engine Australia",
     "https://photos.app.goo.gl/MV5jwRTXuY3P9uEx7", "photo", "Parts Reference", ["2H", "12HT"], []),
    ("Fuel Sedimenter/Water Separator Images",
     "https://photos.app.goo.gl/yTBd1qwecH7oP5L77", "photo", "Reference Photos", ["2H"], []),
    ("2H Block Coolant Drain Location",
     "https://photos.app.goo.gl/qZgrdMhmzyEyMQmh8", "photo", "Reference Photos", ["2H"], []),
    ("12HT Block Coolant Drain Location",
     "https://photos.app.goo.gl/JFZi2xCBwKGZivtu5", "photo", "Reference Photos", ["12HT"], []),
    ("2H/12HT Air Conditioning Compressors",
     "https://photos.app.goo.gl/gZW322EAPcKK2bv5A", "photo", "Reference Photos", ["2H", "12HT"], []),
    ("Images of a Cutaway 2H Engine",
     "https://photos.app.goo.gl/1WpF6M8MffKUnAZ99", "photo", "Reference Photos", ["2H"], []),
    ("Cutaway 2H Engine - Diagrams",
     "https://photos.app.goo.gl/zvkvhhtqL3Bsbpuw6", "photo", "Reference Photos", ["2H"], []),
    ("2H Oil Flow Pathway - Diagram",
     "https://photos.app.goo.gl/3wMxhecVnhAJjGSSA", "photo", "Reference Photos", ["2H"], []),
    ("Vacuum Pump Oil Feed - Identifying Inlet and Outlet",
     "https://photos.app.goo.gl/L6LHJL8kUBydBMGr5", "photo", "Reference Photos", ["2H"], []),
    ("12HT/Late 60 Oil Filter Bypass Valve / Oil Pressure Relief Valve Comparison",
     "https://photos.app.goo.gl/FhEzG6gtKLR6Tn939", "photo", "Reference Photos", ["12HT"], []),
    ("Governor Housing Drain Plug",
     "https://photos.app.goo.gl/a2oYfUFhQnqV9FuQA", "photo", "Reference Photos", ["2H"], []),
    ("2H/12HT Fuel Filter Part Numbers",
     "https://docs.google.com/spreadsheets/d/1NW1dZsgzar10bE5CDiCE9wDawapZakvY_BamvB2_iwc/pubhtml",
     "url", "Parts Reference", ["2H", "12HT"], []),
    ("Fitting an Aftermarket Secondary Filter/Sedimenter to a 2H",
     "https://photos.app.goo.gl/z8mp6CCh2LCCz3Yr9", "photo", "How-To Guide", ["2H"], []),

    # --- Mounts / bellhousing ---
    ("HJ47/HJ60 Engine/Power Steering Mounts",
     "https://photos.app.goo.gl/MyJD7mcHAn4dA5Nr7", "photo", "Reference Photos", [], ["HJ47", "HJ60"]),
    ("HJ47/HJ60/HJ75 Airconditioning Compressor and Idler Mounts",
     "https://photos.app.goo.gl/UDnzbHQUcUXbH2mNA", "photo", "Reference Photos", [], ["HJ47", "HJ60", "HJ75"]),
    ("Identifying HJ47/Early 60 vs Late HJ60/61 Bell Housings",
     "https://photos.app.goo.gl/hnYqW1adf8RiinRj6", "photo", "Reference Photos", [], ["HJ47", "HJ60", "HJ61"]),
    ("2H/12HT Bell Housing Nuts, Bolts, Studs - Torque Specs",
     "https://photos.app.goo.gl/SU4r4Hq44fiDhjTeA", "photo", "Torque Spec", ["2H", "12HT"], []),

    ("2H Oil Pressure Switch (EDIC) vs Oil Pressure Sender",
     "https://photos.app.goo.gl/ebKWHFseRzXL1fGT9", "photo", "Reference Photos", ["2H"], []),
    ("2H Powered Toyota Forklift Images",
     "https://photos.app.goo.gl/kV9548ddDN6tYdKC8", "photo", "Reference Photos", ["2H"], []),
    ("Factory Marketing Images of the 2H Engine",
     "https://photos.app.goo.gl/qbmdogU1JCavqoNp7", "photo", "Reference Photos", ["2H"], []),

    # --- Injection pump ---
    ("2H Manual Injection Pump - Identifying Parts",
     "https://photos.app.goo.gl/RTyKg4YRuijPPYah9", "photo", "Reference Photos", ["2H"], []),
    ("Adjusting the Fuel Control Screw",
     "https://photos.app.goo.gl/HYrrksp6DhKEpK9V6", "photo", "How-To Guide", ["2H"], []),
    ("The Three Positions of the Fuel Control Lever",
     "https://photos.app.goo.gl/aedRVhVoerrQ9tSRA", "photo", "Reference Photos", ["2H"], []),
    ("Lift Pump Rebuild Kit",
     "https://photos.app.goo.gl/ZK8EG8RKu69ghpcaA", "photo", "Parts Reference", ["2H"], []),

    ("2H Oil Filter Cross Reference List",
     "https://docs.google.com/document/d/1eJ_a5gEtkZAuuEiPFczH_RMCSPgWr0IMPsI76MBDbxk/pub",
     "url", "Parts Reference", ["2H"], []),
    ("Valve Adjustment - Page from Service Manual",
     "https://photos.app.goo.gl/qh6eexcvkGeinPcB6", "photo", "Factory Manual", ["2H"], []),
    ("Using a 2H Coupled to an H Bell Housing and 2H Starter Motor",
     "https://photos.app.goo.gl/gU4t4yA3BpE5buiv6", "photo", "Reference Photos", ["2H", "H"], []),
    ("Fitting an Engine Guard to a 2H (Dual Probe Temperature Monitor)",
     "https://photos.app.goo.gl/p257uyz3d4Xat7Ue8", "photo", "How-To Guide", ["2H"], []),
    ("2H Exhaust Manifold Stud Specification",
     "https://photos.app.goo.gl/z1sPUBCfUgXPEvR57", "photo", "Torque Spec", ["2H"], []),
    ("Decoding Toyota Nut/Bolt Part Numbers",
     "https://photos.app.goo.gl/c9BVyXsdsSHHLgdr6", "photo", "Parts Reference", [], []),
    ("2H Tacho Sensor/Pickup Images and Dimensions",
     "https://photos.app.goo.gl/t468jPX18za1G4fa7", "photo", "Reference Photos", ["2H"], []),
    ("2H to 12HT Conversion Guide (by Brennan Stone)",
     "https://docs.google.com/document/d/e/2PACX-1vR-n-JkQh5U6v6OclwS_8arkxtk7froU56j2ig-FmpJw01s5J1snWcJOwlQ_dIH3C7Jt8NyOxv76wT4/pub",
     "url", "How-To Guide", ["2H", "12HT"], []),
    ("A440F 2H/12HT Bell Housing Photos",
     "https://photos.app.goo.gl/GZ3EG9P1nJErzmcc9", "photo", "Reference Photos", ["2H", "12HT"], []),
    ("2H Dipstick Images and Measurements",
     "https://photos.app.goo.gl/agynYb6jRyMHRKcQ8", "photo", "Reference Photos", ["2H"], []),
    ("2H/12HT Belt Diagram",
     "https://photos.app.goo.gl/LqEd1S1SfhBSnVEq9", "photo", "Reference Photos", ["2H", "12HT"], []),
    ("Comprehensive Service Check and Diagnosis Guide (unknown origin)",
     "https://drive.google.com/file/d/1tTqFOmZg7FyTgD-wxeFJgILV4yvDL6lV/view?usp=sharing",
     "url", "Troubleshooting", [], []),

    # --- EDIC ---
    ("EDIC Circuit Diagram",
     "https://drive.google.com/file/d/11a5lB2g3UirvGihyVDqViEZeHDdow-Dc/view?usp=sharing",
     "url", "Factory Manual", ["2H"], []),
    ("Fuel Control Relay - Full Set of Photos",
     "https://photos.app.goo.gl/Ew6QXwQeNijUkghA8", "photo", "Reference Photos", ["2H"], []),
    ("2H Stop Cable Images",
     "https://photos.app.goo.gl/C1cotdMzRNjLqjnm7", "photo", "Reference Photos", ["2H"], []),

    # --- Oil centrifuge ---
    ("Early 2H Oil Centrifuge Part Numbers",
     "https://drive.google.com/open?id=0B-KW6mdxQyjDTTlZanh4b2s5aVU",
     "url", "Parts Reference", ["2H"], []),
    ("Early 2H Oil Centrifuge Images",
     "https://photos.app.goo.gl/3rstP4tjNWgFwHYz5", "photo", "Reference Photos", ["2H"], []),

    # --- Superglow ---
    ("2H Superglow Conceptual Diagram",
     "https://drive.google.com/file/d/1U7OnOI4vGtUV6FS1HlOmdNLPofeletFG/view?usp=sharing",
     "url", "Factory Manual", ["2H"], []),
    ("2H Superglow Wiring Diagram",
     "https://drive.google.com/file/d/1cAugTKCsva9CNNdHNOYRsW_oRnhXL3XD/view?usp=sharing",
     "url", "Factory Manual", ["2H"], []),
    ("2H Superglow Checks - Sheet 1 of 4",
     "https://drive.google.com/file/d/1nX9X6LDHwGPjruHyx2_SG87SDIugC41D/view?usp=sharing",
     "url", "Factory Manual", ["2H"], []),
    ("2H Superglow Checks - Sheet 2 of 4",
     "https://drive.google.com/file/d/1G3bqlQ_V_HE8Wvhzq9SXx59Rd53d27G7/view?usp=sharing",
     "url", "Factory Manual", ["2H"], []),
    ("2H Superglow Checks - Sheet 3 of 4",
     "https://drive.google.com/file/d/1pqJgKKP0Vis8RUXXfKaCVlQIbZXonlb6/view?usp=sharing",
     "url", "Factory Manual", ["2H"], []),
    ("2H Superglow Checks - Sheet 4 of 4",
     "https://drive.google.com/file/d/1xLJCwB69_z74jw6WPQp8dqER19YGNach/view?usp=sharing",
     "url", "Factory Manual", ["2H"], []),
    ("Manual Glow Switch Guide (HJ60, applies to most models)",
     "https://www.hj60.com.au/simplified-glow-system", "url", "How-To Guide", [], ["HJ60"]),

    # --- Torque specs (general, positioned under 2H section) ---
    ("Torque Specifications - All",
     "https://photos.app.goo.gl/VdBFDsD6yR65x6gr5", "photo", "Torque Spec", ["2H"], []),
    ("Torque Specifications - Engine",
     "https://photos.app.goo.gl/1EqEXd86jfTSUBRR9", "photo", "Torque Spec", ["2H"], []),
    ("Torque Specifications - Fuel",
     "https://photos.app.goo.gl/JXUsyVbJmEX8LWGY9", "photo", "Torque Spec", ["2H"], []),
    ("Torque Specifications - Lubrication",
     "https://photos.app.goo.gl/xDQFwRqkkMiLevqw7", "photo", "Torque Spec", ["2H"], []),
    ("Torque Specifications - Cooling",
     "https://photos.app.goo.gl/vLm82MazNoAQ3Pcx7", "photo", "Torque Spec", ["2H"], []),

    # --- How-to guides ---
    ("How to Change Delivery Valve Gaskets",
     "https://docs.google.com/document/d/19SHlXDMITHS1WiQXQa40kXlhrL2GIVzEpbyqhJ73XFk/pub",
     "url", "How-To Guide", ["2H"], []),
    ("How to Change the Injector Pump Diaphragm",
     "https://docs.google.com/document/d/1ZPvljDvzPpgPWnViWyJdNVVkYDdpIe9x_ppJcHW3jX4/pub",
     "url", "How-To Guide", ["2H"], []),
    ("How to Change the Pressure Relief Valve",
     "https://docs.google.com/document/d/14ToAflxRfp2cm1Dy4RHpptTCtucyxJQ6pBI5ZLk1RNk/pub",
     "url", "How-To Guide", ["2H"], []),
    ("How to Find the Engine Number on a 2H Block",
     "https://photos.app.goo.gl/qDkcbSGUzzZtsEXY6", "photo", "How-To Guide", ["2H"], []),
    ("How to Fit a 2H into an HJ45 Chassis",
     "https://docs.google.com/document/d/e/2PACX-1vQBnUiU_6VjKrYfL8-Krxsd7MnG-rmWq1XpmFWZsrljdRGkDueKYRWH3ybN232v4DVrUdsVdsa3znEv/pub",
     "url", "How-To Guide", ["2H"], ["HJ45"]),
    ("How to Fit a 12HT Engine into a 60 Series that had a 3F Engine",
     "https://docs.google.com/document/d/e/2PACX-1vTW0LId1psOd7NIYb-zSySpICRv51VTukKU3IKcV8hHlDpZGDABlzazgSEUT16B70czGY0xs3Z_sYfv/pub",
     "url", "How-To Guide", ["12HT"], ["HJ60"]),
    ("How to Maximise the Performance of a 2H Engine",
     "https://docs.google.com/document/d/1Exax-naX3REHEsphvBW_uUcA14Zf8WolfSzqpenQ7co/pub",
     "url", "How-To Guide", ["2H"], []),

    # --- Frequently encountered issues ---
    ('Starting Problem: "Click, No Crank"',
     "https://docs.google.com/document/d/1z9OWqg7EzNaphjOkt9i0UYwhHKg3VdMqSREhTp1n5A4/pub",
     "url", "Troubleshooting", ["2H"], []),
    ('Starting Problem: "Crank, No Start"',
     "https://docs.google.com/document/d/e/2PACX-1vSFrdV-uLXQVWnnBYtQzMlWL50UUctj_0vDphmpuTO0tRvkdK74CBS50CgpyoXqIrHCgZ4OoKukoJn9/pub",
     "url", "Troubleshooting", ["2H"], []),
    ('Starting Problem: "Starts, but then Stops when Cold"',
     "https://docs.google.com/document/d/19uv1XRihJc72NN8d3LDBU-rtfkuIaGW18qUE6nihXkE/pub",
     "url", "Troubleshooting", ["2H"], []),
    ("Engine Appears to Briefly Lose Power Every 10 Seconds",
     "https://docs.google.com/document/d/1QLOZmfRmmCzph8fZyzs3CgSOZ1VlmX11gMyKRNILOKU/pub",
     "url", "Troubleshooting", ["2H"], []),
    ('The Fuel System is "Sucking Air"',
     "https://docs.google.com/document/d/1qXKR1Vwj5sX6R6tVLRebIYl4J-5uoU4Xd6II2Rfu_9Y/pub",
     "url", "Troubleshooting", ["2H"], []),
    ("Engine Doesn't Shut Down Reliably when the Key is Switched Off",
     "https://docs.google.com/document/d/1YXk5tC9Z4wOdNiRg21nvNlft0dvBzuyn3RT2ndnCNyI/pub",
     "url", "Troubleshooting", ["2H"], []),
    ("Engine is Overheating",
     "https://docs.google.com/document/d/e/2PACX-1vR6wTqIU6-sFFwk2GhLTDwLuDyP2zBaIyQKvyQ2FW2PQv20LNSbFODD458hqcodot9RMeP1czDszoMu/pub",
     "url", "Troubleshooting", ["2H"], []),

    # --- Videos ---
    ("Observing the Fuel Rack Moving Through the Side Inspection Plate",
     "https://www.youtube.com/watch?v=tVFuxBoFC88", "video", "Video", ["2H"], []),
    ("Demonstration: Filling a 2H with Oil Too Quickly Can Hydrolock the Engine",
     "https://www.youtube.com/watch?v=GGqll6SEG-k", "video", "Video", ["2H"], []),
    ("Comparison of Good and Bad Blowby on 2H Engines - Bad",
     "https://www.youtube.com/watch?v=UJ8gKYpOVU4", "video", "Video", ["2H"], []),
    ("Comparison of Good and Bad Blowby on 2H Engines - Good",
     "https://www.youtube.com/watch?v=KwdEdC1YPZQ", "video", "Video", ["2H"], []),
    ("A Look at a Failed Lift Pump",
     "https://youtu.be/Kk_862i004A", "video", "Video", ["2H"], []),
    ("Installing a Wilson Switch (Manual Glow Control) on a Toyota Diesel (3B example)",
     "https://www.youtube.com/watch?v=mxlgqLwYwp8", "video", "Video", ["3B"], []),
    ("Oil Pump Replacement",
     "https://youtu.be/1NI8VLgKg78", "video", "Video", ["2H"], []),
    ("JH Hilux, 12HT Pump Rundown",
     "https://www.youtube.com/watch?v=u3wMYF5hPBM", "video", "Video", ["12HT"], []),
    ("Himalayan Truck - Full 2H Rebuild Playlist",
     "https://youtu.be/MpqTfmYajGw?list=PLWjeGDYf8wY-aZtgQ5Sz7GtIeLXebninN", "video", "Video", ["2H"], []),
    ("2H Rocker Wear",
     "https://www.youtube.com/shorts/dBWNGHAh6b0?feature=share", "video", "Video", ["2H"], []),
    ("Removing Harmonic Balancer Nut Using Starter Motor",
     "https://www.youtube.com/watch?v=rg55zuJtqDo", "video", "Video", ["2H"], []),
    ("Smoke Seen when Cranking with No Glow Operation",
     "https://youtu.be/vyf0B5g20H0", "video", "Video", ["2H"], []),
    ("Bleed Nipple on Fuel Filter Cracked, and Cranking",
     "https://youtu.be/24oFvLK4S2I", "video", "Video", ["2H"], []),
    ("Injector Cracked Open and Cranking",
     "https://youtu.be/8B522JES3TY", "video", "Video", ["2H"], []),
    # NOTE: this one's a joke in the original site (it's the Rickroll video) - see the
    # print warning at the bottom of this script. Left in verbatim; drop it if you'd
    # rather not carry the joke over.
    ("How to Flash the 2H ECU Firmware to Latest Version (fuel economy improvements V5.4.1.2.191-2022)",
     "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "video", "Video", ["2H"], []),

    # --- 12HT specific ---
    ("12HT Vacuum Piping Diagram #1",
     "https://drive.google.com/open?id=1N4xoKPyLyEG3ZJZv6aLcXuM_YCBunkcq",
     "url", "Factory Manual", ["12HT"], []),
    ("12HT Vacuum Piping Diagram #2",
     "https://photos.app.goo.gl/PcaTSGssH2uV5haMA", "photo", "Reference Photos", ["12HT"], []),
    ("12HT Engine Block Images from ADS Injection",
     "https://photos.app.goo.gl/cvRByk76CPs3qTFy5", "photo", "Reference Photos", ["12HT"], []),
    ("Engine Australia Spec Sheet (12HT) - Sheet 1 of 3",
     "https://drive.google.com/file/d/1osxmy-LDG4D6fUpEGYp_MzEQ_KCqDliV/view?usp=sharing",
     "url", "Factory Manual", ["12HT"], []),
    ("Engine Australia Spec Sheet (12HT) - Sheet 2 of 3",
     "https://drive.google.com/file/d/11frl1PNeQkkvmaJnSo1CaQBOz9Sbyga2/view?usp=sharing",
     "url", "Factory Manual", ["12HT"], []),
    ("Engine Australia Spec Sheet (12HT) - Sheet 3 of 3",
     "https://drive.google.com/file/d/1cc4cZkxn2I0ccm_FatArwsSf7lE84DhC/view?usp=sharing",
     "url", "Factory Manual", ["12HT"], []),
    ("Building a 12HT Compression Test Adaptor (Zac Shaw)",
     "https://photos.app.goo.gl/LgWTgHyjSCboJ2ZH7", "photo", "How-To Guide", ["12HT"], []),

    # --- HJ47 ---
    ("HJ47 Wiring Diagram",
     "https://drive.google.com/open?id=0B-KW6mdxQyjDUGphM3BZTXI2Rmc",
     "url", "Factory Manual", [], ["HJ47"]),
    ("HJ47 Radiator Modification when Fitting HJ60 Power Steering",
     "https://photos.app.goo.gl/Ybz4mtatYB9S22dU8", "photo", "How-To Guide", [], ["HJ47", "HJ60"]),

    # --- HJ60/61 ---
    ("Chassis Body Manual (HJ60/61)",
     "https://drive.google.com/open?id=0B-KW6mdxQyjDeXp0aXU3SmFDVUk",
     "url", "Factory Manual", [], ["HJ60", "HJ61"]),
    ("60 Series Maintenance Procedures",
     "https://drive.google.com/open?id=0B-KW6mdxQyjDUFpHV0lwdTdQUDQ",
     "url", "Factory Manual", [], ["HJ60", "HJ61"]),
    ("HJ60 High Res Wiring Diagram (1985)",
     "https://drive.google.com/file/d/1BW5jgT5n8lCW4dabn9LSZvSyhmUDgQ4P/view?usp=sharing",
     "url", "Factory Manual", [], ["HJ60"]),
    ("HJ60/HJ61 High Res Wiring Diagram (1988)",
     "https://drive.google.com/file/d/14Ch8m0Fr1kb3sd0N0-w7aycLOXJthwks/view?usp=drive_link",
     "url", "Factory Manual", [], ["HJ60", "HJ61"]),

    # --- HJ75 ---
    ("HJ75 Wiring Diagram",
     "https://drive.google.com/file/d/1IEbmfO3v3an-pXPZE4CBRdkyWc4taw7b/view?usp=drive_link",
     "url", "Factory Manual", [], ["HJ75"]),

    # --- H engine ---
    ("Engine Repair Manual (98112) - H Engine",
     "https://drive.google.com/file/d/0B-KW6mdxQyjDNHlPUFYyQXUwZTA/view?usp=drive_link&resourcekey=0-2JVrOmRWEDUbRbRkztXN5w",
     "url", "Factory Manual", ["H"], []),
    ("Engine Australia Specification Sheet - H Engine",
     "https://drive.google.com/file/d/0B-KW6mdxQyjDdUxEMUkzNEZKVHc/view?usp=sharing&resourcekey=0-IzWLgsKa0x_xNEFECqV09A",
     "url", "Factory Manual", ["H"], []),
    ("Exploded Parts Diagram - H Engine",
     "https://drive.google.com/file/d/1z3T04dutqhy5ExGV_BoJb7Gb1i2MOQNM/view?usp=sharing",
     "url", "Parts Reference", ["H"], []),

    # --- B engine ---
    ("B/2B Factory Service Manual",
     "https://drive.google.com/file/d/0B-KW6mdxQyjDMUhwRnlTX2tWUXM/view?usp=sharing&resourcekey=0-h3bJntdpLpA0blWwa9vj6A",
     "url", "Factory Manual", ["B", "2B"], []),
    ("B Engine EDIC Factory Service Manual",
     "https://drive.google.com/file/d/1r0SG9TQA-NMAgLkULo1HuLoWlawKbmVN/view?usp=sharing",
     "url", "Factory Manual", ["B"], []),
    ("B Engine - Service/Tune Up Guide",
     "https://drive.google.com/file/d/13zLgOxhtioVq-LGJKtdqHoa33XBe2Qhq/view?usp=sharing",
     "url", "How-To Guide", ["B"], []),
    ("B Series Engine Repair Manual (Inc B/2B/3B) (36047 - Aug 1980)",
     "https://drive.google.com/file/d/1O_Kbk_cc8H6oApkHrDsq8OUh6-XdlzaF/view?usp=drive_link",
     "url", "Factory Manual", ["B", "2B", "3B"], []),
    ("B Engine Guide to Models",
     "https://drive.google.com/file/d/1YwJ9vc5B066RPO3YWn-1drDxD0nQN7WT/view?usp=sharing",
     "url", "Factory Manual", ["B"], []),

    # --- 3B engine ---
    ("3B/13B Factory Service Manual",
     "https://drive.google.com/file/d/0B-KW6mdxQyjDeFdHcy16ZTI4ejQ/view?usp=sharing&resourcekey=0-05C0QxQRst6e_ZozsdOGqw",
     "url", "Factory Manual", ["3B", "13B"], []),

    # --- C/1C-T/2C/2C-T ---
    ("36232E 1C/1C-T, 2C Engine Repair Manual (1983)",
     "https://drive.google.com/file/d/1oiIiFhjpQxdFW0k6nrc7k-_SIeEEIKzB/view?usp=drive_link",
     "url", "Factory Manual", ["1C", "1C-T", "2C"], []),
    ("RM025E 1C/2C/2C-T Engine Repair Manual (1985)",
     "https://drive.google.com/file/d/1SmxU9cAkzdEY_8rfbdHrskLX0_J1dZiG/view?usp=drive_link",
     "url", "Factory Manual", ["1C", "2C", "2C-T"], []),

    # --- L/2L/3L ---
    ("Electrical Wiring Diagram, 1983, Hilux (L/2L)",
     "https://drive.google.com/file/d/1OsxmLbBzLUILrUnQ7fZzIkNmPp9a4Ux7/view?usp=drive_link",
     "url", "Factory Manual", ["L", "2L"], []),
    ("L/2L Factory Service Manual (Aug 1984)",
     "https://drive.google.com/file/d/1dQwSTU68leU8A2yvm40bqgCnIkbJVf_7/view?usp=drive_link",
     "url", "Factory Manual", ["L", "2L"], []),
    ("2L-T/3L Jan 1990 Repair Manual Supplement",
     "https://drive.google.com/file/d/1AFcxMG1igs_vmK0TWzsVDiGy_ceyxS5s/view?usp=sharing",
     "url", "Factory Manual", ["2LT", "3L"], []),
    ("2L-T Factory Service Manuals (folder)",
     "https://drive.google.com/drive/folders/0B-KW6mdxQyjDTUNTcjRyeTBpM2c?resourcekey=0-qZd7_AmRBg62c8N-IMIPKA&usp=sharing",
     "url", "Factory Manual", ["2LT"], []),
    ("2L/3L/5L Late Service Manual (Aug 1997)",
     "https://drive.google.com/file/d/0B-KW6mdxQyjDbk41ZlZjU29SU0E/view?usp=drive_link&resourcekey=0-W8G9-x_7pkV-Hv7BhTRv_A",
     "url", "Factory Manual", ["2L", "3L", "5L"], []),
    ("2L/3L/5L Late Service Manual - Supplement (Jun 1998)",
     "https://drive.google.com/file/d/1pOdTrbWd2pktuzsSm9NM2gXoQxK08-TA/view?usp=sharing",
     "url", "Factory Manual", ["2L", "3L", "5L"], []),
    ("2L/2LT Exploded Parts Diagrams",
     "https://drive.google.com/file/d/0B-KW6mdxQyjDOG03emR6QlVxdmM/view?usp=drive_link&resourcekey=0-BwwXbFuU9qfCHlP0OxnIJQ",
     "url", "Parts Reference", ["2L", "2LT"], []),
    ("2L-TE Cutaway Images",
     "https://photos.app.goo.gl/7yej3eGni8KFCsS36", "photo", "Reference Photos", ["2LT"], []),
    ("Reference: Bosch VE Injection Pump",
     "http://contrails.free.fr/engine_bosch_ve_en.php", "url", "How-To Guide", [], []),
]

# Engine codes referenced above that aren't in the app's default taxonomy.
EXTRA_ENGINES = [
    ('13B', 'B series'), ('1C-T', 'C series'), ('2C-T', 'C series'),
    ('3L', 'L series'), ('5L', 'L series'),
]


def get_or_create_taxonomy():
    for code, family in EXTRA_ENGINES:
        if not EngineModel.query.filter_by(code=code).first():
            db.session.add(EngineModel(code=code, family=family))
    db.session.commit()


def reset_import():
    existing = Resource.query.filter_by(admin_notes=IMPORT_MARKER).all()
    print(f'Removing {len(existing)} previously imported resources...')
    for r in existing:
        db.session.execute(
            db.text('DELETE FROM resources_fts WHERE resource_id = :rid'), {'rid': r.id}
        )
        db.session.delete(r)
    db.session.commit()
    print('Done.')


def run_import(dry_run=False):
    get_or_create_taxonomy()

    admin = User.query.filter_by(is_admin=True).first()
    if admin is None:
        print('WARNING: no admin account exists yet - imported resources will have no reviewer set.')

    categories = {c.name: c for c in Category.query.all()}
    engines = {e.code: e for e in EngineModel.query.all()}
    vehicles = {v.code: v for v in VehicleModel.query.all()}

    missing_categories = {cat for (_, _, _, cat, _, _) in ENTRIES if cat and cat not in categories}
    if missing_categories:
        print(f'ERROR: unknown categories referenced: {missing_categories}')
        return

    print(f'{"Would import" if dry_run else "Importing"} {len(ENTRIES)} resources...')
    if dry_run:
        by_type = {}
        for _, _, rtype, _, _, _ in ENTRIES:
            by_type[rtype] = by_type.get(rtype, 0) + 1
        for t, n in sorted(by_type.items()):
            print(f'  {t}: {n}')
        return

    now = datetime.utcnow()
    for i, (title, url, rtype, cat_name, engine_codes, vehicle_codes) in enumerate(ENTRIES):
        resource = Resource(
            title=title,
            resource_type=rtype,
            url=url,
            category=categories.get(cat_name) if cat_name else None,
            status='approved',
            admin_notes=IMPORT_MARKER,
            reviewed_by=admin,
            created_at=now + timedelta(seconds=i),
            reviewed_at=now + timedelta(seconds=i),
        )
        resource.engine_models = [engines[c] for c in engine_codes if c in engines]
        resource.vehicle_models = [vehicles[c] for c in vehicle_codes if c in vehicles]
        db.session.add(resource)

    db.session.commit()

    count = 0
    for r in Resource.query.filter_by(admin_notes=IMPORT_MARKER).all():
        index_resource(r)
        count += 1

    print(f'Done. Imported and indexed {count} resources.')
    print('\nNote: one entry ("How to Flash the 2H ECU Firmware...") points at what')
    print('looks like a joke link in the original site (a Rickroll). Imported verbatim -')
    print('worth checking /admin/taxonomy or the resource itself if you want to fix or remove it.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--reset', action='store_true', help='Remove a previous import before re-importing')
    parser.add_argument('--dry-run', action='store_true', help='Preview counts only, write nothing')
    args = parser.parse_args()

    with app.app_context():
        ensure_search_index()
        if args.reset:
            reset_import()
        run_import(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
