# Stage 2: Admin Panel & Invitations

This stage builds upon the basic meeting bot by adding:

- **User management** — store users in a `users` table with admin flags.
- **Administration levels** — main admin (hardcoded) and regular admins (can delete meetings, view user lists).
- **Invitation system** — users can invite others to a meeting; invites have statuses: `pending`, `accepted`, `declined`.
- **Meeting participants** — each meeting displays who accepted, declined, or hasn't responded.
- **Change your mind** — participants can change their response status.
- **Delete meetings** — admins can cancel meetings (only if 1 person accepted or if admin).
- **Delete users** — main admin can delete users (removes their invites and user record).

---

## 🆕 What's New in Stage 2

| Feature | Description |
|---------|-------------|
| 👥 **Users table** | Stores `user_id`, `first_name`, `username`, `last_seen`, `is_admin` |
| 🔑 **Admin system** | `main_admin` (hardcoded) can grant/revoke admin rights to others |
| 📋 **User list** | Admins can view all users and delete them |
| 📨 **Invitations** | Users can invite others via inline buttons; invitees receive a private message with accept/decline buttons |
| 📊 **Meeting status** | Meetings show ✅ accepted, 🤨 pending, ❌ declined participants |
| 🔄 **Change status** | Participants can change their response via "Change status" button |
| 🗑️ **Cancel meeting** | Admin or the only accepted participant can cancel a meeting |
| 🧹 **Delete user** | Main admin can delete a user (cleans invites and user entry) |

---

