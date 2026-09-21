window.RV_CONTENT = {
    services: {
        "traffic-analysis": {
            title: "Traffic Analysis",
            icon: "/img/icon/icon-6.png",
            intro: "Lane-wise counts, occupancy, speed bands, and vehicle mix from the CCTV you already operate. Planners and traffic police get today’s corridor picture instead of last month’s manual survey.",
            sections: [
                {
                    heading: "Built for mixed Indian traffic",
                    body: "RoadVision classifies 2W, 3W, cars, LCVs, buses, and trucks in dense, overlapping scenes. Counts are produced per lane and per direction so signal plans and diversion decisions are grounded in evidence."
                },
                {
                    heading: "How it is deployed",
                    body: "We connect ONVIF or RTSP feeds, calibrate each camera to the carriageway, and publish live widgets plus CSV/GIS exports. Edge processing is available where backhaul is limited."
                }
            ],
            bullets: [
                "Junction and mid-block counts with class split",
                "Queue length and occupancy for congestion mapping",
                "Scheduled reports for operations and consultants",
                "Console access for your traffic cell, with 24/7 Unikorn support"
            ]
        },
        "anpr-recognition": {
            title: "ANPR Recognition",
            icon: "/img/icon/icon-8.png",
            intro: "High-accuracy number plate capture for tolling, parking, gated campuses, and enforcement. Unikorn pairs ANPR cameras with the network design so reads are reliable in rain, glare, and night traffic.",
            sections: [
                {
                    heading: "Evidence you can act on",
                    body: "Every read is stored with a plate crop, context frame, timestamp, camera ID, and direction. Operators review exceptions in the RoadVision console instead of scrubbing hours of video."
                },
                {
                    heading: "Integration",
                    body: "We wire ANPR events into boom barriers, parking systems, and watchlists. Local processing keeps plates on your network when policy requires it."
                }
            ],
            bullets: [
                "Entry, exit, and corridor ANPR",
                "Watchlist alerts for stolen or flagged vehicles",
                "Parking and campus access workflows",
                "Certified engineers for camera, IR, and switch layout"
            ]
        },
        "road-condition-ai": {
            title: "Road Condition AI",
            icon: "/img/icon/icon-9.png",
            intro: "Turn patrol dashcams and inspection vehicles into a continuous pavement survey. Potholes, cracks, and faded markings are geotagged so maintenance crews open a map, not a guess.",
            sections: [
                {
                    heading: "From video to work orders",
                    body: "Detections are clustered by location, scored by severity, and exported for GIS or contractor packages. Repeat passes show whether a stretch is worsening."
                },
                {
                    heading: "What we need on site",
                    body: "A stable dashcam or roof camera, GPS, and a simple upload path. Unikorn can supply the camera kit, vehicle networking, and training for your patrol teams."
                }
            ],
            bullets: [
                "Pothole, crack, and marking detection",
                "Geotagged stills for each defect",
                "Corridor heatmaps for annual plans",
                "Support for city, PWD, and contractor fleets"
            ]
        },
        "highway-cctv-intel": {
            title: "Highway CCTV Intel",
            icon: "/img/icon/icon-3.png",
            intro: "Incident, wrong-way, stopped-vehicle, and asset alerts on the IP cameras already lining your corridor. Control rooms see the event with a snapshot, not a wall of silent screens.",
            sections: [
                {
                    heading: "Operations, not just recording",
                    body: "Most highway CCTV is used after the fact. We attach detection to the same streams so ROC / TMC operators are paged while the incident is still live."
                },
                {
                    heading: "Network first",
                    body: "Unikorn’s certified engineers design the backhaul, VLANs, and recording so analytics does not starve the live view. We treat cameras, switches, and power as one system."
                }
            ],
            bullets: [
                "Stopped vehicle, pedestrian, and wrong-way alerts",
                "Camera health and tamper monitoring",
                "Live console plus evidence export",
                "24/7 support for the highway operations team"
            ]
        },
        "fleet-dashcam-survey": {
            title: "Fleet Dashcam Survey",
            icon: "/img/icon/icon-7.png",
            intro: "Every patrol or maintenance drive becomes a mapped survey. Fleets upload video on a schedule; RoadVision returns defect layers and stills without a separate inspection contract for every kilometre.",
            sections: [
                {
                    heading: "Scale without extra crews",
                    body: "If your vehicles already move the corridor, they can collect the evidence. We standardise camera mount, overlap, and naming so results stay comparable week to week."
                },
                {
                    heading: "Delivery",
                    body: "Jobs run in the RoadVision console. Supervisors see progress, download clips, and share geotagged stills with contractors."
                }
            ],
            bullets: [
                "Kit specification and vehicle fitment",
                "Batch upload and job tracking",
                "Mapped defects for the corridors you drive",
                "Training and 24/7 operator support"
            ]
        }
    },
    projects: {
        "highway-corridor": {
            title: "Highway Corridor",
            category: "Complete project",
            headline: "Live CCTV intelligence for a multi-lane expressway stretch",
            image: "/img/portfolio-1.jpg",
            summary: "Existing dome and ANPR cameras on an expressway were recording, but the TMC still learned about incidents from patrol calls. We added detection, health monitoring, and a live console on the same network.",
            challenge: "Mixed vendor cameras, limited backhaul at a few km posts, and operators who could not watch every tile at once.",
            scope: [
                "Network audit and VLAN plan for analytics traffic",
                "Stopped-vehicle and wrong-way models on selected views",
                "Operator console with snapshot evidence",
                "Handover training and 24/7 support window"
            ],
            outcome: "Control room staff now open an alert with a still and camera ID instead of scrubbing NVR footage. Camera downtime is visible the same shift it happens."
        },
        "pavement-survey": {
            title: "Pavement Survey",
            category: "Ongoing project",
            headline: "Dashcam-based pothole and crack mapping for city roads",
            image: "/img/portfolio-2.jpg",
            summary: "A municipal corridor programme needed defect maps faster than a once-a-year consultant survey. Patrol cars already driven by the traffic cell now collect the video.",
            challenge: "Inconsistent camera mounts, no GPS on older vehicles, and no place for engineers to review stills.",
            scope: [
                "Standard dashcam kit and GPS",
                "Weekly upload jobs in the RoadVision console",
                "Geotagged pothole and crack stills",
                "GIS export for the pavement cell"
            ],
            outcome: "Maintenance lists are generated from the latest patrol week. Repeat defects on the same chainage are easy to show contractors."
        },
        "anpr-gate": {
            title: "ANPR Gate",
            category: "Complete project",
            headline: "Plate recognition for parking and restricted-access zones",
            image: "/img/portfolio-3.jpg",
            summary: "A campus needed barrier control without issuing more RFID tags. Unikorn designed the camera, IR, and switching layout, then connected plate events to the existing boom controllers.",
            challenge: "Headlight glare at night, two-wheeler plates, and a network that was never segmented for cameras.",
            scope: [
                "ANPR camera and illuminator placement",
                "Switch, PoE, and recording design",
                "Watchlist and visitor workflows",
                "Evidence snapshots for security"
            ],
            outcome: "Authorised vehicles pass without a tag. Security reviews exceptions from stills instead of standing at the gate with a register."
        },
        "incident-alerts": {
            title: "Incident Alerts",
            category: "Ongoing project",
            headline: "Stopped-vehicle and wrong-way detection on urban flyovers",
            image: "/img/portfolio-4.jpg",
            summary: "Flyover cameras were installed for policing but produced no live alerts. We calibrated the existing PTZs and fixed views, then routed events to the city control room.",
            challenge: "Busy backgrounds, frequent PTZ movement, and operators already overloaded with other feeds.",
            scope: [
                "View lock recommendations for analytics",
                "Stopped and wrong-way detection",
                "Sounding alerts with stills",
                "Weekly tune-up during the first month"
            ],
            outcome: "Wrong-way and stalled vehicles are flagged while traffic is still on the structure, giving police a chance to close a lane before a secondary crash."
        },
        "city-traffic": {
            title: "City Traffic",
            category: "Complete project",
            headline: "Junction counts and classification for signal planning",
            image: "/img/portfolio-5.jpg",
            summary: "Consultants needed classified turning counts at major junctions without a week of enumerators on the median. Junction CCTV was already in place.",
            challenge: "Occlusion from buses, night lighting, and a request for both 15-minute bins and daily totals.",
            scope: [
                "Camera selection and ROI calibration",
                "Classified counts by approach",
                "CSV exports for the signal design team",
                "Console logins for the traffic police cell"
            ],
            outcome: "Signal plans were revised from a full week of counts rather than a single peak-hour sample."
        },
        "fleet-dashcam": {
            title: "Fleet Dashcam",
            category: "Ongoing project",
            headline: "Every patrol drive becomes a mapped road-condition survey",
            image: "/img/portfolio-6.jpg",
            summary: "A highway contractor’s inspection vehicles were filming but the footage sat on SD cards. We put a standard kit on the fleet and run weekly RoadVision jobs.",
            challenge: "Multiple vehicle types, drivers who were not surveyors, and a need for chainage-linked stills.",
            scope: [
                "Fitment and driver briefing",
                "Upload schedule after each shift",
                "Defect clustering along the concession",
                "Sharing folders for independent engineers"
            ],
            outcome: "Pavement evidence is produced as a by-product of patrol, not a separate survey mobilisation."
        }
    }
};
