# **Project Plan: KingShot Kingdom Appointment Planner**

This plan outlines the execution steps required to build and deploy the KingShot Planner on a home server using Python, Flask, and Docker.

## **Milestone 1: Environment & Project Scaffolding**

*Goal: Establish the repository structure and baseline configuration.*

* **Task 1.1:** Initialize project directory and Git repository.  
* **Task 1.2:** Create requirements.txt with flask, gunicorn, and python-dotenv.  
* **Task 1.3:** Setup the Python virtual environment and directory structure (/app, /app/templates, /app/static, /app/data).  
* **Task 1.4:** Create config.py to handle environment variables (e.g., DATABASE\_PATH).  
* **Task 1.5 (Verification):** Run pip install \-r requirements.txt and verify the Flask "Hello World" app runs locally with environment variables loaded.

## **Milestone 2: Database Layer & Event Creation**

*Goal: Implement the persistence layer and the decentralized event creation flow.*

* **Task 2.1:** Implement models.py using sqlite3 to create events, submissions, and assignments tables.  
* **Task 2.2:** Create the **Landing Page (/)** with the "Create New Event" button.  
* **Task 2.3:** Implement the /create POST route to generate unique uids and admin\_secrets.  
* **Task 2.4:** Develop the "Success" view to display the generated Admin and Player URLs.  
* **Task 2.5 (Verification):** Manually create an event through the UI and verify that a new .db file is generated in /app/data with the correct event metadata.

## **Milestone 3: Player Submission Engine**

*Goal: Build the form and logic for players to submit resource data and availability.*

* **Task 3.1:** Build the 49-slot HTML/JS grid with "Paint-to-Select" functionality.  
* **Task 3.2:** Implement dynamic form fields that toggle based on the event type (Construction, Training, Research).  
* **Task 3.3:** Create the /event/\<uid\>/submit route with server-side validation for numeric-only resource inputs.  
* **Task 3.4:** Implement the "Duplicate Check" logic to allow players to update existing submissions using their Player ID.  
* **Task 3.5 (Verification):** Perform a test submission for each event type and verify that the submissions table stores the correct JSON-encoded feasible\_slots array.

## **Milestone 4: Core Logic & Admin Dashboard**

*Goal: Implement the Greedy Algorithm and the protected administrative view.*

* **Task 4.1:** Implement the **Protected Greedy Algorithm** in Python as defined in Section 3 of the Design Doc.  
* **Task 4.2:** Build the Admin Dashboard (/admin/\<uid\>) with basic list views of submissions.  
* **Task 4.3:** Implement administrative controls: Manual Slot Confirmation (Locking) and Submission Deletion.  
* **Task 4.4:** Integrate the "Trigger Redistribution" button to execute the greedy algorithm on unconfirmed slots.  
* **Task 4.5 (Verification):** Create 5 mock submissions with varying resource levels and overlapping slots; trigger redistribution and verify the highest resource player is assigned their preferred slot.

## **Milestone 5: UI Visualizations & Final Polish**

*Goal: Enhance the Admin experience with heatmaps and alliance summaries.*

* **Task 5.1:** Implement the **Demand Heatmap** using CSS opacity based on slot density.  
* **Task 5.2:** Build the **Alliance Impact Summary** table using SQL GROUP BY logic.  
* **Task 5.3:** Add the **Conflict Visualizer** (pulsing red borders) for high-resource waitlisted players.  
* **Task 5.4:** Create the public, read-only "Schedule View" for players to check their status.  
* **Task 5.5 (Verification):** Confirm that the Alliance Summary table correctly aggregates resource totals and that the Heatmap visually identifies the most requested slots.

## **Milestone 6: Dockerization & Deployment**

*Goal: Package the application for a lightweight home server environment.*

* **Task 6.1:** Write the Dockerfile using python:3.12-slim.  
* **Task 6.2:** Create docker-compose.yml with persistent volume mounting for the SQLite database.  
* **Task 6.3:** Perform "Dry Run" deployment: Build image, run container, and verify data persistence across restarts.  
* **Task 6.4:** Execute final manual QA using the Test Cases (TC-ALG-01 through TC-DOC-02) defined in the Design Doc.  
* **Task 6.5 (Verification):** Stop and remove the Docker container, then restart it. Verify that previously created events and assignments are still present in the UI.