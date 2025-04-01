# Second Trial on Schedule Optimization

1. Goal

Given the staffing level and daily schedule for each type of therapist, maximize the total RI minutes (this also shows the average RI minutes).

2. Update

We assume that each patient will receive different treatment times for each category (OT, PT, SLP).

3. Notation
	•	Let P represent the collection of all patients.
	•	Let T represent the collection of all types of therapists.
	•	Let D be the working day of the week.
	•	(New) Let S represent all the continuous time slots during every day’s work time.
For example, S = \{8:00 - 8:15, 8:15 - 8:30, \dots\}.
	•	(New) Let R_{p,d,t} represent the required treatment time for each patient p on day d for the type t.
This should be filled out in the input Excel file.
	•	(New) Let A_{p,t} represent whether patient p’s therapy type t is conducted by therapist k.
	•	C_{k,d,s} is the indicator variable for the availability of therapist k during time slot s on day d, measured in minutes.
	•	If the therapist is Out of Office (OOO), then C_{k,d,s} = 0.
	•	E_k is the working efficiency for every therapist.
For example, during 60 minutes of face-to-face treatment, the true RI time may not necessarily be 60 minutes.
	•	L is the length of a continuous time period.
For example, L = 15 minutes for each session.

4. Decision Variable
	•	(New) The decision variable is an indicator function X_{p,k,t,d,s} that equals 1 if and only if patient p receives treatment of type t from therapist k at time slot s on day d.

5. Objective Function
	•	We simplify the modeling process by accounting for the fact that therapists do not necessarily devote 100% of their time to face-to-face treatment (e.g., they also handle documentation, emails, etc.).

6. Constraints

6.1 Hard KPI: Satisfying Patients’ Weekly Requirement
	•	The required treatment time should be satisfied each day.

6.2 Limitation of Therapists’ Accessibility
	•	A therapist will be assigned only if they are available.
	•	Given an available time slot, only one patient can be assigned.

6.3 Time Conflict
	•	A therapist can only be assigned to one patient at a time during any given working period.

6.4 Patient Continuity Constraint
	•	Ensures that once a therapist is assigned to a patient, that patient continues treatment with the same therapist whenever possible.

6.5 Lunch Time Constraint
	•	No treatment will be scheduled between 12:00 PM and 1:00 PM.