# Prototype threat model

The finite prototype assumes that the operating system, SQLite file permissions, HMAC secrets, trusted permit issuer, and evaluator process are not controlled by the acting model. It does not claim protection when an attacker can alter the Python source, read the shared HMAC key, directly modify the database, or invoke trusted issuer code.

The executor checks an action against an HMAC permit bound to the action, destination, complete state, and persisted policy. It consumes a nonce and advances the local snapshot in one SQLite transaction. Its local effect record is idempotent. A real external receiver must independently deduplicate the nonce and support reconciliation after crashes.

Signed exports bind state, policy, clock, completed effects, and pending dispatch metadata. They are integrity-protected, not automatically fresh or authoritative. A production handoff needs an authenticated source, monotonic epochs, an import protocol, and receiver-side effect reconciliation.

The local evaluator process is an interface boundary only. Production evaluator custody requires separate credentials and deployment authority.
