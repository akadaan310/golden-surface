Versioned migrations. `schema.sql` is v1 and is applied on first run.
Each `NNN_name.sql` here is applied once, in order, when
`PRAGMA user_version` < NNN; user_version is then set to NNN.
Never edit an applied migration; add a new file.
