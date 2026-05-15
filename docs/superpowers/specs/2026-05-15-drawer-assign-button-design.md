# Drawer Assign Button Design

## 1. Overview
Streamline the admin assignment workflow by adding an "Assign" button to the player detail drawer. This allows admins to quickly assign or reassign players to a slot after tapping it in the heatmap.

## 2. Goals
- Add an "Assign" button for each player in the selection drawer.
- Implement AJAX-based assignment to avoid full page reloads.
- Show a confirmation prompt if the slot is already occupied.
- Maintain visual consistency with existing "Lock/Unlock" buttons.

## 3. Architecture & Components

### 3.1 Backend Updates (Python)
- **Data Structure:** Update the `slot_players` dictionary to include `submission_id` for each player entry.
- **Route Compatibility:** Ensure the existing `manual_assign` route is compatible with AJAX requests (it already returns 302, which the existing `handleFormSubmit` logic handles by fetching the redirect target).

### 3.2 Frontend Updates (HTML/JS)
- **Drawer Template:** Update the JavaScript template literal that renders the drawer content to include the "Assign" button.
- **Assignment Logic:**
  - Create a JavaScript function `assignFromDrawer(day, slotIndex, submissionId, playerName)`.
  - Logic to detect existing assignments for the slot.
  - Logic to trigger the `manual_assign` POST request via AJAX.
- **Visual Feedback:** Use the existing dynamic content refresh logic to update the heatmap and drawer.

### 3.3 Confirmation Workflow
1. User taps slot.
2. User clicks "Assign" next to a player in the drawer.
3. JS checks if the slot has an existing assignment (using the data already present in the DOM or JSON).
4. If occupied, `confirm()` dialog: "Slot already assigned to [Name]. Replace?"
5. On confirm, send POST to `/admin/<uid>/manual_assign`.

## 4. Testing Strategy
- **Manual Test:** Tap an empty slot, assign a player, verify highlight and name change.
- **Manual Test:** Tap an occupied slot, assign a different player, verify confirmation prompt and successful swap.
- **Regression:** Verify that the "Refresh Player Data" and "Assign Appointments" buttons still work correctly.

## 5. Security & Constraints
- Continue using the `secret` token and CSRF protection for all assignment actions.
