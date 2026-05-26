"""Authentication & identity domain.

Owns the ``users`` table. Auth is delegated to Clerk (see CLAUDE.md §3);
this domain stores the provider + stable subject and the canonical email.
"""
