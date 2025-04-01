#!/usr/bin/env python3
"""
Therapy Schedule Optimization using Google OR-Tools

This script implements the therapy scheduling optimization problem as described in problem.md.
It uses Google's CP-SAT solver to maximize total RI (Reportable and Billable) minutes
while satisfying all constraints for patient treatment and therapist availability.
"""

from ortools.sat.python import cp_model
import json
import numpy as np
import pandas as pd
import time
import argparse
from datetime import datetime, timedelta
import os
import shutil

class TherapyScheduler:
    """Class for the therapy scheduling optimization problem."""
    
    def __init__(self, data_file):
        """Initialize with data from a JSON file."""
        self.load_data(data_file)
        self.setup_indices()
        print(f"Loaded data for {self.num_patients} patients, {self.num_therapists} therapists, "
              f"{self.num_therapist_types} therapy types, {self.num_days} days, and {self.slots_per_day} slots per day.")
    
    def load_data(self, data_file):
        """Load data from a JSON file."""
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        # Basic parameters
        self.num_patients = data['num_patients']
        self.num_therapist_types = data['num_therapist_types']
        self.num_therapists = data['num_therapists']
        self.num_days = data['num_days']
        self.slots_per_day = data['slots_per_day']
        self.slot_length = data['slot_length']
        self.lunch_start = data['lunch_start']
        self.lunch_end = data['lunch_end']
        
        # Input data arrays
        self.R = np.array(data['R'])  # Required treatment time [day, patient, therapy_type]
        self.A = np.array(data['A'])  # Whether patient requires therapy type [patient, therapy_type]
        self.therapist_type = np.array(data['therapist_type'])  # Therapist type mapping [therapist, type]
        self.C = np.array(data['C'])  # Therapist availability [therapist, day, slot]
        self.E = np.array(data['E'])  # Efficiency factors [therapist]
    
    def setup_indices(self):
        """Set up index ranges for model variables."""
        self.P = range(self.num_patients)  # Patients
        self.T = range(self.num_therapist_types)  # Therapy types
        self.K = range(self.num_therapists)  # Therapists
        self.D = range(self.num_days)  # Days
        self.S = range(self.slots_per_day)  # Time slots
    
    def create_model(self):
        """Create the optimization model with all constraints."""
        model = cp_model.CpModel()
        
        # Decision Variables: X[p, k, t, d, s]
        # 1 if patient p gets therapy t from therapist k at slot s on day d
        X = {}
        for p in self.P:
            for k in self.K:
                for t in self.T:
                    for d in self.D:
                        for s in self.S:
                            X[p, k, t, d, s] = model.NewBoolVar(f'X_p{p}_k{k}_t{t}_d{d}_s{s}')
        
        # Objective: Maximize total RI minutes and satisfaction of treatment requirements
        objective_terms = []
        
        # Regular RI minutes terms
        for p in self.P:
            for k in self.K:
                for t in self.T:
                    for d in self.D:
                        for s in self.S:
                            # Higher weight (5x) for meeting requirements
                            if self.A[p, t] == 1 and self.R[d, p, t] > 0:
                                # If this patient needs this therapy on this day, give extra weight
                                objective_terms.append(X[p, k, t, d, s] * self.slot_length * self.E[k] * 5)
                            else:
                                # Regular weight for additional therapy
                                objective_terms.append(X[p, k, t, d, s] * self.slot_length * self.E[k])
        
        # Maximize the objective function
        model.Maximize(sum(objective_terms))
        
        # Constraints
        
        # 1. Only allow treatments for required therapy types
        for p in self.P:
            for t in self.T:
                if self.A[p, t] == 0:  # Patient doesn't need this therapy type
                    for k in self.K:
                        for d in self.D:
                            for s in self.S:
                                model.Add(X[p, k, t, d, s] == 0)
        
        # 2. Upper bound on treatment time
        # This prevents over-treatment beyond what's beneficial
        for p in self.P:
            for t in self.T:
                for d in self.D:
                    if self.A[p, t] == 1 and self.R[d, p, t] > 0:
                        # Sum up all slots assigned to this patient for this therapy on this day
                        treatment_time = sum(X[p, k, t, d, s] * self.slot_length for k in self.K for s in self.S)
                        # Allow at most 50% more than required (convert to integer)
                        max_treatment = int(min(self.R[d, p, t] * 1.5, self.slots_per_day * self.slot_length))
                        model.Add(treatment_time <= max_treatment)
        
        # 3. Limitation of Therapists' Accessibility
        # 3.1 Therapist can only be assigned if they are available
        for k in self.K:
            for d in self.D:
                for s in self.S:
                    if self.C[k, d, s] == 0:  # Therapist not available
                        for p in self.P:
                            for t in self.T:
                                model.Add(X[p, k, t, d, s] == 0)
        
        # 3.2 Given an available time slot, only one patient can be assigned
        for k in self.K:
            for d in self.D:
                for s in self.S:
                    model.Add(sum(X[p, k, t, d, s] for p in self.P for t in self.T) <= 1)
        
        # 4. Time Conflict: A patient can only receive one therapy at a time
        for p in self.P:
            for d in self.D:
                for s in self.S:
                    model.Add(sum(X[p, k, t, d, s] for k in self.K for t in self.T) <= 1)
        
        # 5. Therapist can only provide therapy of their type
        for p in self.P:
            for k in self.K:
                for t in self.T:
                    if self.therapist_type[k, t] == 0:  # Therapist k can't provide therapy t
                        for d in self.D:
                            for s in self.S:
                                model.Add(X[p, k, t, d, s] == 0)
        
        # 6. Lunch Time Constraint: No therapy during lunch
        for s in range(self.lunch_start, self.lunch_end + 1):
            if s < self.slots_per_day:
                for p in self.P:
                    for k in self.K:
                        for t in self.T:
                            for d in self.D:
                                model.Add(X[p, k, t, d, s] == 0)
        
        # 7. Patient Continuity: Same therapist for same patient and therapy type across days
        for p in self.P:
            for t in self.T:
                if self.A[p, t] == 0:  # Skip if patient doesn't need this therapy
                    continue
                
                # Creates a variable for each therapist that might treat this patient
                treats_patient = {}
                for k in self.K:
                    if self.therapist_type[k, t] == 1:  # Only consider therapists of the right type
                        treats_patient[k] = model.NewBoolVar(f'treats_p{p}_t{t}_k{k}')
                        
                        # This therapist treats this patient if they have at least one session
                        all_sessions = []
                        for d in self.D:
                            for s in self.S:
                                all_sessions.append(X[p, k, t, d, s])
                        
                        model.Add(sum(all_sessions) > 0).OnlyEnforceIf(treats_patient[k])
                        model.Add(sum(all_sessions) == 0).OnlyEnforceIf(treats_patient[k].Not())
                
                # Ensure at most one therapist per patient per therapy type
                model.Add(sum(treats_patient.values()) <= 1)
        
        # 8. Continuity: Simplify to ensure there are no gaps in treatment sessions
        for p in self.P:
            for k in self.K:
                for t in self.T:
                    for d in self.D:
                        # Only apply for valid combinations
                        if self.A[p, t] == 0 or self.therapist_type[k, t] == 0 or self.R[d, p, t] == 0:
                            continue
                        
                        # Get all slots where this therapy happens
                        therapy_slots = []
                        for s in self.S:
                            therapy_slots.append(X[p, k, t, d, s])
                        
                        # If any therapy happens, create session continuity
                        therapy_happens = model.NewBoolVar(f'therapy_p{p}_k{k}_t{t}_d{d}')
                        model.Add(sum(therapy_slots) > 0).OnlyEnforceIf(therapy_happens)
                        model.Add(sum(therapy_slots) == 0).OnlyEnforceIf(therapy_happens.Not())
                        
                        # Enforce session continuity (no gaps except for lunch)
                        # Create variables to track first and last slots of therapy
                        for s1 in self.S:
                            if self.lunch_start <= s1 <= self.lunch_end:
                                continue  # Skip lunch slots
                                
                            is_first = model.NewBoolVar(f'first_p{p}_k{k}_t{t}_d{d}_s{s1}')
                            
                            # If this is the first slot, then:
                            # 1. This slot has therapy
                            # 2. All earlier non-lunch slots have no therapy
                            conditions = [X[p, k, t, d, s1]]
                            for s2 in self.S:
                                if s2 < s1 and not (self.lunch_start <= s2 <= self.lunch_end):
                                    conditions.append(X[p, k, t, d, s2].Not())
                            
                            # If all conditions are true, this is the first slot
                            model.AddBoolAnd(conditions).OnlyEnforceIf(is_first)
                            
                            # Create last slot variable similarly
                            is_last = model.NewBoolVar(f'last_p{p}_k{k}_t{t}_d{d}_s{s1}')
                            
                            conditions = [X[p, k, t, d, s1]]
                            for s2 in self.S:
                                if s2 > s1 and not (self.lunch_start <= s2 <= self.lunch_end):
                                    conditions.append(X[p, k, t, d, s2].Not())
                            
                            model.AddBoolAnd(conditions).OnlyEnforceIf(is_last)
                            
                            # For each potential first and last slot combination, ensure everything in between has therapy
                            for s2 in self.S:
                                if s2 > s1 and not (self.lunch_start <= s1 <= self.lunch_end) and not (self.lunch_start <= s2 <= self.lunch_end):
                                    is_first_last_pair = model.NewBoolVar(f'pair_p{p}_k{k}_t{t}_d{d}_s{s1}_s{s2}')
                                    model.AddBoolAnd([is_first, is_last]).OnlyEnforceIf(is_first_last_pair)
                                    
                                    # For all slots between first and last (excluding lunch), make sure they have therapy
                                    for s3 in range(s1 + 1, s2):
                                        if not (self.lunch_start <= s3 <= self.lunch_end):
                                            model.Add(X[p, k, t, d, s3] == 1).OnlyEnforceIf(is_first_last_pair)
        
        return model, X
    
    def solve_model(self, model, X, time_limit=300.0):
        """Solve the optimization model."""
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        
        print(f"Starting optimization with {time_limit} seconds time limit...")
        start_time = time.time()
        status = solver.Solve(model)
        solve_time = time.time() - start_time
        print(f"Optimization completed in {solve_time:.2f} seconds with status: {solver.StatusName(status)}")
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            # Calculate objective value
            total_ri_minutes = 0
            schedule_data = []
            for p in self.P:
                for k in self.K:
                    for t in self.T:
                        for d in self.D:
                            for s in self.S:
                                if solver.Value(X[p, k, t, d, s]) > 0:
                                    total_ri_minutes += self.slot_length * self.E[k]
                                    schedule_data.append({
                                        "Patient": p + 1,
                                        "Day": d + 1,
                                        "Slot": s + 1,
                                        "Time": self.format_time(s),
                                        "Therapist": k + 1,
                                        "Therapy Type": t + 1,
                                        "RI Minutes": self.slot_length * self.E[k]
                                    })
            
            # Print results
            print(f"Total RI Minutes: {total_ri_minutes}")
            print(f"Average RI Minutes Per Patient: {total_ri_minutes / self.num_patients:.2f}")
            
            return {
                "status": solver.StatusName(status),
                "total_ri_minutes": total_ri_minutes,
                "average_ri_minutes": total_ri_minutes / self.num_patients,
                "solve_time": solve_time,
                "schedule": schedule_data
            }
        else:
            print(f"Failed to find a solution. Status: {solver.StatusName(status)}")
            return None
    
    def format_time(self, slot):
        """Convert slot number to time string (assuming 8:00 AM start)."""
        start_time = datetime(2023, 1, 1, 8, 0, 0)  # Arbitrary date with 8:00 AM
        minutes_to_add = slot * self.slot_length
        time_value = start_time + timedelta(minutes=minutes_to_add)
        return time_value.strftime("%H:%M")
    
    def print_schedule(self, results):
        """Print the schedule in a readable format."""
        if not results or "schedule" not in results:
            print("No schedule to print.")
            return
        
        schedule_df = pd.DataFrame(results["schedule"])
        
        # Sort by day, patient, time
        schedule_df = schedule_df.sort_values(by=["Day", "Patient", "Slot"])
        
        # Print summary
        print("\nSchedule Summary:")
        print(f"Total RI Minutes: {results['total_ri_minutes']}")
        print(f"Average RI Minutes Per Patient: {results['average_ri_minutes']:.2f}")
        print(f"Solution Status: {results['status']}")
        print(f"Solve Time: {results['solve_time']:.2f} seconds")
        
        # Print schedule by day
        print("\nDetailed Schedule:")
        for day in sorted(schedule_df["Day"].unique()):
            print(f"\nDay {day}:")
            
            day_schedule = schedule_df[schedule_df["Day"] == day]
            for patient in sorted(day_schedule["Patient"].unique()):
                patient_schedule = day_schedule[day_schedule["Patient"] == patient]
                print(f"\n  Patient {patient}:")
                
                for _, row in patient_schedule.iterrows():
                    therapy_type = "OT" if row["Therapy Type"] == 1 else "PT" if row["Therapy Type"] == 2 else "SLP"
                    print(f"    {row['Time']} - {therapy_type} with Therapist {row['Therapist']}")
    
    def save_results(self, results, output_file):
        """Save results to a JSON file and create a folder structure."""
        if not results:
            print("No results to save.")
            return
        
        # Create results directory if it doesn't exist
        results_dir = os.path.dirname(output_file) if os.path.dirname(output_file) else "results"
        os.makedirs(results_dir, exist_ok=True)
        
        # Save JSON results
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {output_file}")
        
        # Create summary markdown file
        schedule_df = pd.DataFrame(results["schedule"])
        markdown_output = os.path.join(results_dir, os.path.splitext(os.path.basename(output_file))[0] + "_summary.md")
        
        with open(markdown_output, 'w') as md_file:
            md_file.write(f"# Therapy Schedule Optimization Results\n\n")
            md_file.write(f"## Summary Statistics\n\n")
            md_file.write(f"- **Input Dataset**: {self.data_file}\n")
            md_file.write(f"- **Output File**: {os.path.basename(output_file)}\n")
            md_file.write(f"- **Total RI Minutes**: {results['total_ri_minutes']:.2f}\n")
            md_file.write(f"- **Average RI Minutes Per Patient**: {results['average_ri_minutes']:.2f}\n")
            md_file.write(f"- **Solution Status**: {results['status']}\n")
            md_file.write(f"- **Solve Time**: {results['solve_time']:.2f} seconds\n\n")
            
            # Add dataset parameters
            md_file.write(f"## Dataset Parameters\n\n")
            md_file.write(f"- **Patients**: {self.num_patients}\n")
            md_file.write(f"- **Therapists**: {self.num_therapists}\n")
            md_file.write(f"- **Therapy Types**: {self.num_therapist_types}\n")
            md_file.write(f"- **Days**: {self.num_days}\n")
            md_file.write(f"- **Slots Per Day**: {self.slots_per_day}\n")
            md_file.write(f"- **Slot Length**: {self.slot_length} minutes\n\n")
            
            md_file.write(f"## Schedule Details\n\n")
            
            # Sort by day, patient, time
            schedule_df = schedule_df.sort_values(by=["Day", "Patient", "Slot"])
            
            # Group by therapy type to get statistics
            therapy_counts = schedule_df["Therapy Type"].value_counts()
            therapy_minutes = schedule_df.groupby("Therapy Type")["RI Minutes"].sum()
            
            md_file.write("### Therapy Type Statistics\n\n")
            md_file.write("| Therapy Type | Sessions | Total Minutes |\n")
            md_file.write("|-------------|----------|---------------|\n")
            for t_type in sorted(therapy_counts.index):
                therapy_name = "OT" if t_type == 1 else "PT" if t_type == 2 else "SLP"
                md_file.write(f"| {therapy_name} | {therapy_counts[t_type]} | {therapy_minutes[t_type]:.2f} |\n")
            
            md_file.write("\n### Detailed Daily Schedule\n\n")
            
            for day in sorted(schedule_df["Day"].unique()):
                md_file.write(f"#### Day {day}\n\n")
                
                day_schedule = schedule_df[schedule_df["Day"] == day]
                for patient in sorted(day_schedule["Patient"].unique()):
                    md_file.write(f"**Patient {patient}**\n\n")
                    
                    patient_schedule = day_schedule[day_schedule["Patient"] == patient]
                    for _, row in patient_schedule.iterrows():
                        therapy_type = "OT" if row["Therapy Type"] == 1 else "PT" if row["Therapy Type"] == 2 else "SLP"
                        md_file.write(f"- {row['Time']} - {therapy_type} with Therapist {row['Therapist']}\n")
                    
                    md_file.write("\n")
                
                md_file.write("\n")
            
        print(f"Markdown summary saved to {markdown_output}")
    
    def run(self, time_limit=300.0, output_file=None):
        """Run the optimization and return results."""
        model, X = self.create_model()
        results = self.solve_model(model, X, time_limit)
        
        if results:
            self.print_schedule(results)
            
            if output_file:
                self.save_results(results, output_file)
            else:
                # Default output file if none specified
                results_dir = "results"
                os.makedirs(results_dir, exist_ok=True)
                file_basename = os.path.splitext(os.path.basename(self.data_file))[0]
                output_file = os.path.join(results_dir, f"schedule_{file_basename}.json")
                self.save_results(results, output_file)
        
        return results

def main():
    parser = argparse.ArgumentParser(description='Therapy Schedule Optimization')
    parser.add_argument('data_file', help='Path to JSON data file')
    parser.add_argument('--output', '-o', help='Path to output JSON file')
    parser.add_argument('--output-dir', '-d', default='results', help='Directory to save results (default: results)')
    parser.add_argument('--time-limit', '-t', type=float, default=300.0, help='Time limit in seconds (default: 300)')
    args = parser.parse_args()
    
    # Ensure the input directory exists
    input_dir = os.path.dirname(args.data_file)
    if input_dir == '':
        # If no directory specified, check if file exists in input directory
        input_path = os.path.join('input', args.data_file)
        if os.path.exists(input_path):
            args.data_file = input_path
    
    # Set up output file
    if args.output:
        output_file = args.output
    else:
        os.makedirs(args.output_dir, exist_ok=True)
        file_basename = os.path.splitext(os.path.basename(args.data_file))[0]
        output_file = os.path.join(args.output_dir, f"schedule_{file_basename}.json")
    
    # Initialize scheduler with the data file
    scheduler = TherapyScheduler(args.data_file)
    # Store the data file path
    scheduler.data_file = args.data_file
    scheduler.run(time_limit=args.time_limit, output_file=output_file)

if __name__ == "__main__":
    # Create input and results directories if they don't exist
    for dir_name in ['input', 'results']:
        os.makedirs(dir_name, exist_ok=True)
    
    main() 