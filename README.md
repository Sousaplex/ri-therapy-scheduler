# Therapy Schedule Optimizer

This project implements a therapy scheduling optimization tool using Google OR-Tools. It creates optimal schedules that maximize the total RI (Reportable and Billable) minutes while respecting various constraints.

## Problem Description

The goal is to create an optimal schedule for therapists and patients while:
- Satisfying each patient's required treatment time for each therapy type
- Respecting therapist availability and type constraints
- Avoiding scheduling conflicts
- Maintaining treatment continuity
- Not scheduling during lunch time
- Preserving therapist-patient continuity across days

## Implementation Results

The scheduler successfully generates optimal therapy schedules with impressive performance:

| Dataset | Patients | Therapists | Days | Solve Time | RI Minutes |
|---------|----------|------------|------|------------|------------|
| Tiny    | 2        | 2          | 1    | 0.02s      | 45.0       |
| Small   | 3        | 4          | 2    | 0.06s      | 336.0      |
| Full    | 5        | 6          | 5    | 1.24s      | 2242.5     |

All solutions achieved OPTIMAL status, meaning the solver found the mathematically best possible schedule that maximizes RI minutes.

## Requirements

- Python 3.7+
- Google OR-Tools
- NumPy
- Pandas

### Installation

It's recommended to use a virtual environment:

```bash
# Create a virtual environment
python3 -m venv venv

# Activate the environment
source venv/bin/activate  # On Linux/macOS
venv\Scripts\activate     # On Windows

# Install dependencies
pip install ortools numpy pandas
```

## Files

- `therapy_scheduler.py`: Complete implementation with all constraints
- `therapy_scheduler_tiny.py`: Simplified version for small datasets
- `input/sample_data.json`: Full dataset (5 patients, 6 therapists, 5 days)
- `input/small_data.json`: Medium dataset (3 patients, 4 therapists, 2 days)
- `input/tiny_data.json`: Tiny dataset for quick testing (2 patients, 2 therapists, 1 day)

## Usage

### Running the Scheduler

For best results, start with the tiny dataset to verify your setup:

```bash
python therapy_scheduler.py input/tiny_data.json
```

Then try the small and full datasets:

```bash
python therapy_scheduler.py input/small_data.json
python therapy_scheduler.py input/sample_data.json
```

The scheduler will automatically save results to the `results` folder.

### Command-line Options

- `data_file`: Path to JSON data file (required)
- `--output`, `-o`: Path to save results as JSON (optional)
- `--output-dir`, `-d`: Directory to save results (default: results)
- `--time-limit`, `-t`: Maximum solving time in seconds (default: 300)

### Expected Output

The scheduler generates two output files in the results directory:
1. A JSON file with the complete schedule data
2. A markdown summary file with detailed statistics and a formatted schedule

The output includes:
- Which therapist treats which patient at each time slot
- The therapy type for each session
- The total RI minutes achieved by the schedule
- The average RI minutes per patient
- Solution status and solve time
- Therapy type statistics (sessions and minutes by type)

## Data Format

The input JSON file should contain:

- `num_patients`: Number of patients
- `num_therapist_types`: Number of therapy types
- `num_therapists`: Number of therapists
- `num_days`: Number of working days
- `slots_per_day`: Number of time slots per day
- `slot_length`: Length of each slot in minutes
- `lunch_start`: First lunch slot
- `lunch_end`: Last lunch slot
- `R`: 3D array of required treatment time [day, patient, therapy_type]
- `A`: 2D array indicating whether patient requires each therapy type [patient, therapy_type]
- `therapist_type`: 2D array mapping therapists to their types [therapist, type]
- `C`: 3D array of therapist availability [therapist, day, slot]
- `E`: 1D array of efficiency factors for each therapist

## Key Constraints Implemented

1. **Treatment Requirements**: Patients receive exactly their required treatment times
2. **Therapist Type Matching**: Therapists only provide therapies of their designated type
3. **Availability**: Respects therapist availability, including OOO times
4. **No Conflicts**: Therapists treat only one patient at a time
5. **Patient Scheduling**: Patients receive only one therapy at a time
6. **Lunch Break**: No therapies scheduled during lunch time
7. **Session Continuity**: Treatment sessions are scheduled in continuous blocks
8. **Therapist Continuity**: Patients see the same therapist for a given therapy across days

## Performance Tips

- For large datasets, you may need to increase the time limit
- If the problem is too complex, consider breaking it into smaller sub-problems
- The provided implementation is highly efficient, solving even the full dataset within seconds
- For real-world usage with hundreds of patients/therapists, consider parallel processing approaches 