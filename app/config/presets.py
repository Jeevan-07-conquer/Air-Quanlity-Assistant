"""Labeled sample/demo profile presets (SRD FR-03)."""

from typing import Any, TypedDict


class SamplePreset(TypedDict):
    id: str
    badge: str
    title: str
    subtitle: str
    location_id: str
    profile_summary: str
    profile: dict[str, Any]


SAMPLE_PRESETS: list[SamplePreset] = [
    {
        "id": "delhi-working-professional",
        "badge": "Sample profile",
        "title": "Delhi working professional",
        "subtitle": "Delhi • Public transit commute • Office hours",
        "location_id": "delhi",
        "profile_summary": "Adult commuter using metro/bus with morning errands and evening return.",
        "profile": {
            "household": ["adult"],
            "vulnerabilities": [],
            "primaryActivities": ["commute", "errands"],
            "commuteMode": "public_transit",
            "commuteTime": "morning",
            "outdoorWorkerOrAthlete": False,
            "indoorContext": {
                "purifierAvailable": True,
                "indoorSensorAvailable": False,
                "cookingExposure": False,
                "ventilationConstraints": False,
            },
            "plannedOutdoorActivity": {
                "activity": "Morning metro commute and evening grocery errand",
                "preferredPeriod": "morning",
            },
            "priorities": ["Safer commute timing", "Reliable indoor ventilation window"],
            "isSamplePreset": True,
            "presetId": "delhi-working-professional",
            "presetLabel": "Sample profile: Delhi working professional",
        },
    },
    {
        "id": "noida-family-toddler-senior",
        "badge": "Sample profile",
        "title": "Noida family with toddler and senior",
        "subtitle": "Noida • Vulnerable household • Air purifier available",
        "location_id": "noida",
        "profile_summary": "Household with a toddler and senior citizen; needs conservative outdoor & ventilation guidance.",
        "profile": {
            "household": ["adult", "child", "senior"],
            "vulnerabilities": ["respiratory_condition"],
            "primaryActivities": ["school", "errands"],
            "commuteMode": "car",
            "commuteTime": "morning",
            "outdoorWorkerOrAthlete": False,
            "indoorContext": {
                "purifierAvailable": True,
                "indoorSensorAvailable": True,
                "cookingExposure": True,
                "ventilationConstraints": True,
            },
            "plannedOutdoorActivity": {
                "activity": "Short park walk with toddler and morning school drop-off",
                "preferredPeriod": "morning",
            },
            "priorities": ["Protect toddler and senior", "Indoor air quality control"],
            "isSamplePreset": True,
            "presetId": "noida-family-toddler-senior",
            "presetLabel": "Sample profile: Noida family with toddler and senior",
        },
    },
    {
        "id": "mumbai-outdoor-athlete",
        "badge": "Sample profile",
        "title": "Mumbai outdoor athlete",
        "subtitle": "Mumbai • Morning run • High exertion",
        "location_id": "mumbai",
        "profile_summary": "Endurance runner planning morning outdoor training; sensitive to exertion windows.",
        "profile": {
            "household": ["adult"],
            "vulnerabilities": [],
            "primaryActivities": ["sports", "commute"],
            "commuteMode": "two_wheeler",
            "commuteTime": "morning",
            "outdoorWorkerOrAthlete": True,
            "indoorContext": {
                "purifierAvailable": False,
                "indoorSensorAvailable": False,
                "cookingExposure": False,
                "ventilationConstraints": False,
            },
            "plannedOutdoorActivity": {
                "activity": "10 km morning outdoor run",
                "preferredPeriod": "morning",
            },
            "priorities": ["Safe exertion window", "Lower-exposure training alternatives"],
            "isSamplePreset": True,
            "presetId": "mumbai-outdoor-athlete",
            "presetLabel": "Sample profile: Mumbai outdoor athlete",
        },
    },
    {
        "id": "kolkata-mixed-commute",
        "badge": "Sample profile",
        "title": "Kolkata mixed commute household",
        "subtitle": "Kolkata • School & errands • Mixed transport",
        "location_id": "kolkata",
        "profile_summary": "Household balancing school drop-off, walking, and transit without an indoor sensor.",
        "profile": {
            "household": ["adult", "child"],
            "vulnerabilities": [],
            "primaryActivities": ["commute", "school", "errands"],
            "commuteMode": "mixed",
            "commuteTime": "morning",
            "outdoorWorkerOrAthlete": False,
            "indoorContext": {
                "purifierAvailable": False,
                "indoorSensorAvailable": False,
                "cookingExposure": True,
                "ventilationConstraints": False,
            },
            "plannedOutdoorActivity": {
                "activity": "Walking school run and afternoon market errand",
                "preferredPeriod": "afternoon",
            },
            "priorities": ["Practical transit swaps", "Safe cooking ventilation"],
            "isSamplePreset": True,
            "presetId": "kolkata-mixed-commute",
            "presetLabel": "Sample profile: Kolkata mixed commute household",
        },
    },
]
