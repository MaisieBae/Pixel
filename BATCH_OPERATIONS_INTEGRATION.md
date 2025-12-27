# Batch Operations Integration Guide

This guide explains how to integrate the new batch operations feature into your Pixel bot admin console.

## Overview

The batch operations feature allows you to add or subtract points and XP from multiple users at once. This is useful for:
- Event bonuses (e.g., "Everyone gets 500 points!")
- Corrections (e.g., fixing point/XP errors)
- Seasonal rewards
- Community goals
- Testing

## Files Created

### 1. Backend Logic
- **`app/admin/batch_operations.py`** - Core batch operation functions
  - `batch_adjust_points()` - Adjust points for multiple users
  - `batch_adjust_xp()` - Adjust XP for multiple users

### 2. API Endpoints
- **`app/admin/server_batch_addon.txt`** - API endpoint code to add to `server.py`
  - `POST /admin/api/users/batch-points` - Batch points operation
  - `POST /admin/api/users/batch-xp` - Batch XP operation

### 3. UI Components
- **`app/admin/templates/admin_batch_ui_addon.html`** - UI code to add to admin template
  - New "Batch Operations" tab
  - Forms for points and XP operations
  - Results display with success/failure counts

## Integration Steps

### Step 1: Add API Endpoints to server.py

1. Open `app/admin/server.py`
2. Find line ~320 (after the `api_users_xp_transactions` endpoint)
3. Insert the code from `app/admin/server_batch_addon.txt`

The code should be placed after this section:
```python
@admin.get("/api/users/xp/transactions")
async def api_users_xp_transactions(...):
    # existing code
```

And before this section:
```python
# ---------- Settings Management (v2.1.0) ----------
```

### Step 2: Add UI to Admin Template

1. Open `app/admin/templates/admin_index_v120.html`
2. **Add the tab button** (around line 186, in the tab navigation):
   ```html
   <button class="tab" data-tab="batch">⚡ Batch Operations</button>
   ```

3. **Add the tab content** (before the closing `</div>` of the container, after the Settings tab):
   - Copy the entire tab content section from `admin_batch_ui_addon.html`
   - Paste it before `</div>` that closes the main container

4. **Add the JavaScript** (at the end of the existing `<script>` tag):
   - Copy the JavaScript section from `admin_batch_ui_addon.html`
   - Paste it at the end of the existing `<script>` block

### Step 3: Test the Integration

1. Restart your Pixel bot
2. Navigate to `/admin` in your browser
3. Look for the "⚡ Batch Operations" tab
4. Try a test operation:
   - Select "Add Points"
   - Enter a small amount (e.g., 10)
   - Choose "Specific Users"
   - Enter one user ID
   - Click "Execute Batch Operation"

## Feature Capabilities

### Batch Points
- **Add or subtract** any amount of points
- Target **all users** or **specific users** (by ID)
- Optional **allow negative balances**
- Custom **reason** for audit trail
- Shows success/failure counts
- Lists any errors encountered

### Batch XP
- **Add or subtract** any amount of XP
- Target **all users** or **specific users** (by ID)
- Automatically handles **level changes**
- Custom **reason** for audit trail
- Shows success/failure counts
- Displays level ups/downs
- Lists any errors encountered

## API Documentation

### POST /admin/api/users/batch-points

**Parameters:**
- `operation` (required): "add" or "subtract"
- `amount` (required): Positive integer
- `target` (required): "all" or "specific"
- `user_ids` (optional): Comma-separated user IDs (required if target="specific")
- `reason` (optional): String for transaction log (default: "batch_admin")
- `allow_negative` (optional): Boolean (default: false)

**Response:**
```json
{
  "ok": true,
  "total_users": 10,
  "success": 9,
  "failed": 1,
  "errors": [
    {
      "user_id": 5,
      "user_name": "JohnDoe",
      "error": "Insufficient points"
    }
  ]
}
```

### POST /admin/api/users/batch-xp

**Parameters:**
- `operation` (required): "add" or "subtract"
- `amount` (required): Positive integer
- `target` (required): "all" or "specific"
- `user_ids` (optional): Comma-separated user IDs (required if target="specific")
- `reason` (optional): String for transaction log (default: "batch_admin")

**Response:**
```json
{
  "ok": true,
  "total_users": 10,
  "success": 10,
  "failed": 0,
  "errors": [],
  "level_ups": [
    {
      "user_name": "Alice",
      "level_before": 5,
      "level_after": 6
    }
  ]
}
```

## Safety Features

1. **Confirmation prompt** - User must confirm before executing
2. **Transaction logging** - All operations logged in audit trail
3. **Error handling** - Individual failures don't stop the entire batch
4. **Negative balance protection** - Prevents users from going into debt (for points)
5. **Clear feedback** - Shows exactly what succeeded and what failed
6. **Warning messages** - UI displays important notes about batch operations

## Usage Examples

### Example 1: Event Bonus for All Users
```
Operation: Add
Amount: 1000
Target: All Users
Reason: Holiday Event Bonus
```

### Example 2: Correction for Specific Users
```
Operation: Subtract
Amount: 50
Target: Specific Users
User IDs: 12, 15, 23
Reason: Points correction - duplicate award
```

### Example 3: XP Boost Event
```
Operation: Add
Amount: 2000
Target: All Users
Reason: Anniversary XP Boost
```

## Troubleshooting

### "No user IDs provided" error
- Make sure to enter at least one user ID when using "Specific Users"
- Format: `1, 2, 3` or just `5`

### "Insufficient points" errors
- Some users don't have enough points to subtract
- Enable "Allow negative balances" if you want to proceed anyway

### Users not affected
- Check that user IDs are correct
- Verify users exist in database
- Check audit logs for transaction records

## Notes

- All batch operations are **irreversible** through the UI
- Use the audit logs to track what was changed
- Test with small amounts on specific users first
- The page auto-refreshes after successful operations
- All operations maintain referential integrity with the database

## Version

Batch Operations Feature v1.0
Added: December 26, 2024
Compatible with: Pixel Bot v2.1.0+
