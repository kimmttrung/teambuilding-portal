# 03 – Mô hình dữ liệu v2 (SQLite)

> DDL chuẩn được xuất từ SQLite sau Alembic revision `c24a29db2026`.
> File lịch sử: [03-legacy-data-model.md](03-legacy-data-model.md).
> Mapping bảng cũ → mới, giới hạn ORM/API và cách seed:
> [16-schema-v2-handoff.md](16-schema-v2-handoff.md).

**24 bảng** (không tính `alembic_version`; `schema_archive` là bảng thứ 24).
Thời gian UTC ISO-8601, SQLite bật `foreign_keys=ON`, WAL và `busy_timeout`
theo `backend/app/core/database.py`. JSON lưu dưới dạng TEXT.
`registrations.room_id` hiện chưa có FK cứng: SQLite không thêm được FK cho
bảng cũ qua ALTER TABLE; cần kiểm tra phòng ở service trước khi ghi.
**ORM và service cũ chưa chuyển theo DDL này**; không chạy ứng dụng với DB v2.

## 1. Danh sách bảng và DDL

### `audit_logs`

```sql
CREATE TABLE audit_logs (
	id INTEGER NOT NULL,
	event_id INTEGER,
	actor_id INTEGER,
	action VARCHAR(64) NOT NULL,
	entity_type VARCHAR(64) NOT NULL,
	entity_id INTEGER,
	before_data TEXT,
	after_data TEXT,
	reason TEXT,
	ip_address VARCHAR(64),
	created_at VARCHAR(32) NOT NULL,
	CONSTRAINT pk_audit_logs PRIMARY KEY (id),
	CONSTRAINT fk_audit_logs_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id),
	CONSTRAINT fk_audit_logs_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE
);
```

### `bus_assignments`

```sql
CREATE TABLE bus_assignments (
	id INTEGER NOT NULL,
	registration_id INTEGER NOT NULL,
	bus_id INTEGER NOT NULL,
	trip_leg_id INTEGER NOT NULL,
	assignment_mode VARCHAR(16) NOT NULL,
	assigned_by INTEGER,
	assigned_at VARCHAR(32) NOT NULL,
	note TEXT,
	CONSTRAINT pk_bus_assignments PRIMARY KEY (id),
	CONSTRAINT ck_bus_assignments_mode_valid CHECK (assignment_mode IN ('auto', 'manual')),
	CONSTRAINT fk_bus_assignments_assigned_by_users FOREIGN KEY(assigned_by) REFERENCES users (id),
	CONSTRAINT fk_bus_assignments_bus_id_buses FOREIGN KEY(bus_id) REFERENCES buses (id),
	CONSTRAINT fk_bus_assignments_registration_id_registrations FOREIGN KEY(registration_id) REFERENCES registrations (id) ON DELETE CASCADE,
	CONSTRAINT fk_bus_assignments_trip_leg_id_trip_legs FOREIGN KEY(trip_leg_id) REFERENCES trip_legs (id),
	CONSTRAINT uq_bus_assignments_registration_leg UNIQUE (registration_id, trip_leg_id)
);
```

### `buses`

```sql
CREATE TABLE buses (
	id INTEGER NOT NULL,
	event_id INTEGER NOT NULL,
	trip_leg_id INTEGER NOT NULL,
	bus_code VARCHAR(32) NOT NULL,
	plate_number VARCHAR(32),
	capacity INTEGER NOT NULL,
	pickup_point_id INTEGER,
	dropoff_point VARCHAR(255),
	gather_time VARCHAR(32),
	departure_time VARCHAR(32),
	leader_user_id INTEGER,
	leader_name VARCHAR(255),
	leader_phone VARCHAR(32),
	driver_name VARCHAR(255),
	driver_phone VARCHAR(32),
	linked_flight_id INTEGER,
	note TEXT,
	created_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	CONSTRAINT pk_buses PRIMARY KEY (id),
	CONSTRAINT ck_buses_capacity_positive CHECK (capacity > 0),
	CONSTRAINT fk_buses_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
	CONSTRAINT fk_buses_leader_user_id_users FOREIGN KEY(leader_user_id) REFERENCES users (id),
	CONSTRAINT fk_buses_linked_flight_id_flights FOREIGN KEY(linked_flight_id) REFERENCES flights (id),
	CONSTRAINT fk_buses_pickup_point_id_pickup_points FOREIGN KEY(pickup_point_id) REFERENCES pickup_points (id),
	CONSTRAINT fk_buses_trip_leg_id_trip_legs FOREIGN KEY(trip_leg_id) REFERENCES trip_legs (id),
	CONSTRAINT uq_buses_event_leg_code UNIQUE (event_id, trip_leg_id, bus_code)
);
```

### `departments`

```sql
CREATE TABLE departments (
	id INTEGER NOT NULL,
	code VARCHAR(32) NOT NULL,
	name VARCHAR(255) NOT NULL,
	display_order INTEGER NOT NULL,
	is_active BOOLEAN NOT NULL,
	CONSTRAINT pk_departments PRIMARY KEY (id),
	CONSTRAINT uq_departments_code UNIQUE (code)
);
```

### `email_logs`

```sql
CREATE TABLE "email_logs" (
	id INTEGER NOT NULL,
	user_id INTEGER,
	to_email VARCHAR(255) NOT NULL,
	template VARCHAR(64) NOT NULL,
	subject VARCHAR(255) NOT NULL,
	body_preview TEXT,
	status VARCHAR(16) NOT NULL,
	error_message TEXT,
	retry_count INTEGER NOT NULL,
	related_type VARCHAR(64),
	related_id INTEGER,
	sent_at VARCHAR(32),
	created_at VARCHAR(32) NOT NULL,
	event_id INTEGER,
	CONSTRAINT pk_email_logs PRIMARY KEY (id),
	CONSTRAINT ck_email_logs_status_valid CHECK (status IN ('queued', 'sent', 'failed')),
	CONSTRAINT fk_email_logs_user_id_users FOREIGN KEY(user_id) REFERENCES users (id),
	CONSTRAINT fk_email_logs_event_id_events FOREIGN KEY(event_id) REFERENCES events (id)
);
```

### `events`

```sql
CREATE TABLE events (
	id INTEGER NOT NULL,
	code VARCHAR(32) NOT NULL,
	name VARCHAR(255) NOT NULL,
	destination VARCHAR(255),
	start_date VARCHAR(10) NOT NULL,
	end_date VARCHAR(10) NOT NULL,
	status VARCHAR(32) NOT NULL,
	registration_opens_at VARCHAR(32),
	registration_closes_at VARCHAR(32),
	terms_version VARCHAR(16) NOT NULL,
	terms_content TEXT,
	banner_url VARCHAR(512),
	is_active BOOLEAN NOT NULL,
	created_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL, settings_json TEXT, itinerary_json TEXT, documents_json TEXT, announcements_json TEXT,
	CONSTRAINT pk_events PRIMARY KEY (id),
	CONSTRAINT ck_events_status_valid CHECK (status IN ('draft', 'registration_open', 'registration_closed', 'allocation_processing', 'information_published', 'event_started', 'completed')),
	CONSTRAINT uq_events_code UNIQUE (code)
);
```

### `flight_assignments`

```sql
CREATE TABLE flight_assignments (
	id INTEGER NOT NULL,
	registration_id INTEGER NOT NULL,
	flight_id INTEGER NOT NULL,
	direction VARCHAR(16) NOT NULL,
	seat_number VARCHAR(8),
	ticket_code VARCHAR(32),
	assignment_mode VARCHAR(16) NOT NULL,
	assigned_by INTEGER,
	assigned_at VARCHAR(32) NOT NULL,
	note TEXT,
	CONSTRAINT pk_flight_assignments PRIMARY KEY (id),
	CONSTRAINT ck_flight_assignments_mode_valid CHECK (assignment_mode IN ('auto', 'manual')),
	CONSTRAINT ck_flight_assignments_direction_valid CHECK (direction IN ('outbound', 'return')),
	CONSTRAINT fk_flight_assignments_assigned_by_users FOREIGN KEY(assigned_by) REFERENCES users (id),
	CONSTRAINT fk_flight_assignments_flight_id_flights FOREIGN KEY(flight_id) REFERENCES flights (id),
	CONSTRAINT fk_flight_assignments_registration_id_registrations FOREIGN KEY(registration_id) REFERENCES registrations (id) ON DELETE CASCADE,
	CONSTRAINT uq_flight_assignments_registration_direction UNIQUE (registration_id, direction)
);
```

### `flights`

```sql
CREATE TABLE flights (
	id INTEGER NOT NULL,
	event_id INTEGER NOT NULL,
	flight_code VARCHAR(16) NOT NULL,
	airline VARCHAR(128),
	direction VARCHAR(16) NOT NULL,
	shift_id INTEGER,
	departure_airport VARCHAR(8) NOT NULL,
	arrival_airport VARCHAR(8) NOT NULL,
	departure_time VARCHAR(32) NOT NULL,
	arrival_time VARCHAR(32) NOT NULL,
	capacity INTEGER NOT NULL,
	reserved_slots INTEGER NOT NULL,
	note TEXT,
	is_active BOOLEAN NOT NULL,
	created_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	CONSTRAINT pk_flights PRIMARY KEY (id),
	CONSTRAINT ck_flights_direction_valid CHECK (direction IN ('outbound', 'return')),
	CONSTRAINT ck_flights_capacity_non_negative CHECK (capacity >= 0),
	CONSTRAINT ck_flights_reserved_within_capacity CHECK (reserved_slots <= capacity),
	CONSTRAINT ck_flights_reserved_non_negative CHECK (reserved_slots >= 0),
	CONSTRAINT fk_flights_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
	CONSTRAINT fk_flights_shift_id_shifts FOREIGN KEY(shift_id) REFERENCES shifts (id),
	CONSTRAINT uq_flights_event_code_direction_time UNIQUE (event_id, flight_code, direction, departure_time)
);
```

### `gala_layouts`

```sql
CREATE TABLE gala_layouts (
	id INTEGER NOT NULL,
	event_id INTEGER NOT NULL,
	name VARCHAR(255) NOT NULL,
	venue VARCHAR(255),
	starts_at VARCHAR(32),
	stage_position VARCHAR(16) NOT NULL,
	grid_width INTEGER NOT NULL,
	grid_height INTEGER NOT NULL,
	selection_status VARCHAR(16) NOT NULL,
	turn_seconds INTEGER NOT NULL,
	hold_seconds INTEGER NOT NULL,
	draw_seed INTEGER,
	created_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL, draw_orders_json TEXT,
	CONSTRAINT pk_gala_layouts PRIMARY KEY (id),
	CONSTRAINT ck_gala_layouts_selection_status_valid CHECK (selection_status IN ('closed', 'drawing', 'open', 'finalized')),
	CONSTRAINT ck_gala_layouts_hold_seconds_positive CHECK (hold_seconds > 0),
	CONSTRAINT fk_gala_layouts_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE
);
```

### `gala_seats`

```sql
CREATE TABLE gala_seats (
	id INTEGER NOT NULL,
	table_id INTEGER NOT NULL,
	seat_number INTEGER NOT NULL,
	is_available BOOLEAN NOT NULL, hold_json TEXT, assignment_json TEXT,
	CONSTRAINT pk_gala_seats PRIMARY KEY (id),
	CONSTRAINT fk_gala_seats_table_id_gala_tables FOREIGN KEY(table_id) REFERENCES gala_tables (id) ON DELETE CASCADE,
	CONSTRAINT uq_gala_seats_table_number UNIQUE (table_id, seat_number)
);
```

### `gala_tables`

```sql
CREATE TABLE gala_tables (
	id INTEGER NOT NULL,
	layout_id INTEGER NOT NULL,
	table_code VARCHAR(16) NOT NULL,
	table_name VARCHAR(128),
	seat_count INTEGER NOT NULL,
	pos_x INTEGER NOT NULL,
	pos_y INTEGER NOT NULL,
	is_vip BOOLEAN NOT NULL,
	is_available BOOLEAN NOT NULL,
	CONSTRAINT pk_gala_tables PRIMARY KEY (id),
	CONSTRAINT ck_gala_tables_seat_count_positive CHECK (seat_count > 0),
	CONSTRAINT fk_gala_tables_layout_id_gala_layouts FOREIGN KEY(layout_id) REFERENCES gala_layouts (id) ON DELETE CASCADE,
	CONSTRAINT uq_gala_tables_layout_code UNIQUE (layout_id, table_code)
);
```

### `hotels`

```sql
CREATE TABLE hotels (
	id INTEGER NOT NULL,
	event_id INTEGER NOT NULL,
	name VARCHAR(255) NOT NULL,
	address VARCHAR(512),
	phone VARCHAR(32),
	check_in_at VARCHAR(32),
	check_out_at VARCHAR(32),
	map_url VARCHAR(512),
	note TEXT,
	created_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	CONSTRAINT pk_hotels PRIMARY KEY (id),
	CONSTRAINT fk_hotels_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE
);
```

### `login_attempts`

```sql
CREATE TABLE login_attempts (
	id INTEGER NOT NULL,
	email VARCHAR(255) NOT NULL,
	ip_address VARCHAR(64) NOT NULL,
	succeeded BOOLEAN NOT NULL,
	attempted_at VARCHAR(32) NOT NULL,
	CONSTRAINT pk_login_attempts PRIMARY KEY (id)
);
```

### `pickup_points`

```sql
CREATE TABLE pickup_points (
	id INTEGER NOT NULL,
	event_id INTEGER NOT NULL,
	trip_leg_id INTEGER,
	work_location_id INTEGER,
	name VARCHAR(255) NOT NULL,
	address VARCHAR(512),
	map_url VARCHAR(512),
	display_order INTEGER NOT NULL,
	CONSTRAINT pk_pickup_points PRIMARY KEY (id),
	CONSTRAINT fk_pickup_points_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
	CONSTRAINT fk_pickup_points_trip_leg_id_trip_legs FOREIGN KEY(trip_leg_id) REFERENCES trip_legs (id),
	CONSTRAINT fk_pickup_points_work_location_id_work_locations FOREIGN KEY(work_location_id) REFERENCES work_locations (id)
);
```

### `refresh_tokens`

```sql
CREATE TABLE refresh_tokens (
	id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	jti VARCHAR(64) NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	issued_at VARCHAR(32) NOT NULL,
	expires_at VARCHAR(32) NOT NULL,
	revoked_at VARCHAR(32),
	revoked_reason VARCHAR(32),
	user_agent VARCHAR(255),
	ip_address VARCHAR(64),
	CONSTRAINT pk_refresh_tokens PRIMARY KEY (id),
	CONSTRAINT fk_refresh_tokens_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
```

### `registration_cancellations`

```sql
CREATE TABLE registration_cancellations (
	id INTEGER NOT NULL,
	event_id INTEGER NOT NULL,
	registration_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	mode VARCHAR(16) NOT NULL,
	status VARCHAR(16) NOT NULL,
	reason VARCHAR(512) NOT NULL,
	event_status VARCHAR(32) NOT NULL,
	after_deadline BOOLEAN NOT NULL,
	requested_at VARCHAR(32) NOT NULL,
	decided_by INTEGER,
	decided_at VARCHAR(32),
	decision_note VARCHAR(1000),
	penalty_applied BOOLEAN NOT NULL,
	penalty_note VARCHAR(512),
	released_items TEXT,
	created_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	CONSTRAINT pk_registration_cancellations PRIMARY KEY (id),
	CONSTRAINT ck_registration_cancellations_mode_valid CHECK (mode IN ('self', 'request', 'admin')),
	CONSTRAINT ck_registration_cancellations_status_valid CHECK (status IN ('pending', 'approved', 'rejected', 'withdrawn')),
	CONSTRAINT fk_registration_cancellations_decided_by_users FOREIGN KEY(decided_by) REFERENCES users (id),
	CONSTRAINT fk_registration_cancellations_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
	CONSTRAINT fk_registration_cancellations_registration_id_registrations FOREIGN KEY(registration_id) REFERENCES registrations (id) ON DELETE CASCADE,
	CONSTRAINT fk_registration_cancellations_user_id_users FOREIGN KEY(user_id) REFERENCES users (id)
);
```

### `registrations`

```sql
CREATE TABLE registrations (
	id INTEGER NOT NULL,
	event_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	is_participating BOOLEAN NOT NULL,
	not_participating_reason VARCHAR(512),
	shift_id INTEGER,
	is_shift_locked BOOLEAN NOT NULL,
	departure_location_id INTEGER,
	wish_note TEXT,
	companion_count INTEGER NOT NULL,
	status VARCHAR(16) NOT NULL,
	submitted_at VARCHAR(32),
	cancelled_at VARCHAR(32),
	cancel_reason VARCHAR(512),
	penalty_applied BOOLEAN NOT NULL,
	created_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL, bus_needs_json TEXT, consents_json TEXT, room_assignment_json TEXT, room_id INTEGER,
	CONSTRAINT pk_registrations PRIMARY KEY (id),
	CONSTRAINT ck_registrations_status_valid CHECK (status IN ('draft', 'submitted', 'cancelled')),
	CONSTRAINT ck_registrations_companion_non_negative CHECK (companion_count >= 0),
	CONSTRAINT fk_registrations_departure_location_id_work_locations FOREIGN KEY(departure_location_id) REFERENCES work_locations (id),
	CONSTRAINT fk_registrations_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
	CONSTRAINT fk_registrations_shift_id_shifts FOREIGN KEY(shift_id) REFERENCES shifts (id),
	CONSTRAINT fk_registrations_user_id_users FOREIGN KEY(user_id) REFERENCES users (id),
	CONSTRAINT uq_registrations_event_user UNIQUE (event_id, user_id)
);
```

### `rooms`

```sql
CREATE TABLE rooms (
	id INTEGER NOT NULL,
	hotel_id INTEGER NOT NULL,
	room_number VARCHAR(32) NOT NULL,
	room_type VARCHAR(32),
	capacity INTEGER NOT NULL,
	floor VARCHAR(16),
	gender_policy VARCHAR(16) NOT NULL,
	note VARCHAR(512),
	CONSTRAINT pk_rooms PRIMARY KEY (id),
	CONSTRAINT ck_rooms_gender_policy_valid CHECK (gender_policy IN ('any', 'male', 'female')),
	CONSTRAINT ck_rooms_capacity_positive CHECK (capacity > 0),
	CONSTRAINT fk_rooms_hotel_id_hotels FOREIGN KEY(hotel_id) REFERENCES hotels (id) ON DELETE CASCADE,
	CONSTRAINT uq_rooms_hotel_number UNIQUE (hotel_id, room_number)
);
```

### `schema_archive`

```sql
CREATE TABLE schema_archive (
	id INTEGER NOT NULL,
	source_table VARCHAR(64) NOT NULL,
	source_id INTEGER NOT NULL,
	payload TEXT NOT NULL,
	archived_at VARCHAR(32) NOT NULL,
	CONSTRAINT pk_schema_archive PRIMARY KEY (id),
	CONSTRAINT uq_schema_archive_source UNIQUE (source_table, source_id)
);
```

### `shifts`

```sql
CREATE TABLE shifts (
	id INTEGER NOT NULL,
	event_id INTEGER NOT NULL,
	code VARCHAR(16) NOT NULL,
	name VARCHAR(128) NOT NULL,
	description VARCHAR(512),
	earliest_departure VARCHAR(5),
	display_order INTEGER NOT NULL,
	CONSTRAINT pk_shifts PRIMARY KEY (id),
	CONSTRAINT fk_shifts_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
	CONSTRAINT uq_shifts_event_code UNIQUE (event_id, code)
);
```

### `teams`

```sql
CREATE TABLE teams (
	id INTEGER NOT NULL,
	code VARCHAR(32) NOT NULL,
	name VARCHAR(255) NOT NULL,
	department_id INTEGER,
	leader_user_id INTEGER,
	color VARCHAR(16),
	is_active BOOLEAN NOT NULL,
	created_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	CONSTRAINT pk_teams PRIMARY KEY (id),
	CONSTRAINT fk_teams_department_id_departments FOREIGN KEY(department_id) REFERENCES departments (id),
	CONSTRAINT uq_teams_code UNIQUE (code)
);
```

### `trip_legs`

```sql
CREATE TABLE trip_legs (
	id INTEGER NOT NULL,
	event_id INTEGER NOT NULL,
	code VARCHAR(32) NOT NULL,
	name VARCHAR(255) NOT NULL,
	direction VARCHAR(16) NOT NULL,
	leg_date VARCHAR(10),
	is_airport_linked BOOLEAN NOT NULL,
	display_order INTEGER NOT NULL,
	CONSTRAINT pk_trip_legs PRIMARY KEY (id),
	CONSTRAINT ck_trip_legs_direction_valid CHECK (direction IN ('outbound', 'return')),
	CONSTRAINT fk_trip_legs_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
	CONSTRAINT uq_trip_legs_event_code UNIQUE (event_id, code)
);
```

### `users`

```sql
CREATE TABLE users (
	id INTEGER NOT NULL,
	employee_code VARCHAR(32),
	email VARCHAR(255) NOT NULL,
	password_hash VARCHAR(255),
	sso_subject VARCHAR(255),
	role VARCHAR(32) NOT NULL,
	full_name VARCHAR(255) NOT NULL,
	display_name VARCHAR(255),
	avatar_url VARCHAR(512),
	phone VARCHAR(32),
	personal_email VARCHAR(255),
	gender VARCHAR(16),
	date_of_birth VARCHAR(10),
	address VARCHAR(512),
	team_id INTEGER,
	department_id INTEGER,
	work_location_id INTEGER,
	job_title VARCHAR(128),
	join_date VARCHAR(10),
	id_card_number VARCHAR(32),
	id_card_type VARCHAR(16),
	id_card_issue_date VARCHAR(10),
	id_card_issue_place VARCHAR(255),
	shirt_size VARCHAR(8),
	dietary_restriction VARCHAR(255),
	health_note TEXT,
	emergency_contact_name VARCHAR(255),
	emergency_contact_phone VARCHAR(32),
	is_active BOOLEAN NOT NULL,
	must_change_password BOOLEAN NOT NULL,
	last_login_at VARCHAR(32),
	created_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at VARCHAR(32) DEFAULT (CURRENT_TIMESTAMP) NOT NULL, failed_login_count INTEGER NOT NULL, locked_until VARCHAR(32), chat_history_json TEXT,
	CONSTRAINT pk_users PRIMARY KEY (id),
	CONSTRAINT ck_users_gender_valid CHECK (gender IS NULL OR gender IN ('male', 'female', 'other')),
	CONSTRAINT ck_users_role_valid CHECK (role IN ('employee', 'team_leader', 'admin', 'super_admin')),
	CONSTRAINT fk_users_department_id_departments FOREIGN KEY(department_id) REFERENCES departments (id),
	CONSTRAINT fk_users_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (id),
	CONSTRAINT fk_users_work_location_id_work_locations FOREIGN KEY(work_location_id) REFERENCES work_locations (id),
	CONSTRAINT uq_users_sso_subject UNIQUE (sso_subject)
);
```

### `work_locations`

```sql
CREATE TABLE work_locations (
	id INTEGER NOT NULL,
	code VARCHAR(16) NOT NULL,
	name VARCHAR(255) NOT NULL,
	city VARCHAR(128),
	airport_code VARCHAR(8),
	display_order INTEGER NOT NULL,
	is_active BOOLEAN NOT NULL,
	CONSTRAINT pk_work_locations PRIMARY KEY (id),
	CONSTRAINT uq_work_locations_code UNIQUE (code)
);
```

## 2. Index tường minh

```sql
CREATE INDEX ix_audit_logs_action ON audit_logs (action);
CREATE INDEX ix_audit_logs_actor_time ON audit_logs (actor_id, created_at);
CREATE INDEX ix_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX ix_audit_logs_event_id ON audit_logs (event_id);
CREATE INDEX ix_bus_assignments_bus_id ON bus_assignments (bus_id);
CREATE INDEX ix_bus_assignments_registration_id ON bus_assignments (registration_id);
CREATE INDEX ix_buses_event_id ON buses (event_id);
CREATE INDEX ix_buses_linked_flight_id ON buses (linked_flight_id);
CREATE INDEX ix_buses_trip_leg_id ON buses (trip_leg_id);
CREATE INDEX ix_email_logs_event_id ON email_logs (event_id);
CREATE INDEX ix_email_logs_status ON email_logs (status);
CREATE INDEX ix_email_logs_template ON email_logs (template);
CREATE INDEX ix_email_logs_user_id ON email_logs (user_id);
CREATE INDEX ix_events_is_active ON events (is_active);
CREATE INDEX ix_events_status ON events (status);
CREATE INDEX ix_flight_assignments_flight_id ON flight_assignments (flight_id);
CREATE INDEX ix_flight_assignments_registration_id ON flight_assignments (registration_id);
CREATE INDEX ix_flights_direction ON flights (direction);
CREATE INDEX ix_flights_event_id ON flights (event_id);
CREATE INDEX ix_flights_shift_id ON flights (shift_id);
CREATE INDEX ix_gala_layouts_event_id ON gala_layouts (event_id);
CREATE INDEX ix_gala_seats_table_id ON gala_seats (table_id);
CREATE INDEX ix_gala_tables_layout_id ON gala_tables (layout_id);
CREATE INDEX ix_hotels_event_id ON hotels (event_id);
CREATE INDEX ix_login_attempts_attempted_at ON login_attempts (attempted_at);
CREATE INDEX ix_login_attempts_email_ip_time ON login_attempts (email, ip_address, attempted_at);
CREATE INDEX ix_login_attempts_ip_time ON login_attempts (ip_address, attempted_at);
CREATE INDEX ix_pickup_points_event_id ON pickup_points (event_id);
CREATE INDEX ix_pickup_points_trip_leg_id ON pickup_points (trip_leg_id);
CREATE INDEX ix_refresh_tokens_expires_at ON refresh_tokens (expires_at);
CREATE UNIQUE INDEX ix_refresh_tokens_jti ON refresh_tokens (jti);
CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX ix_registration_cancellations_event_id ON registration_cancellations (event_id);
CREATE INDEX ix_registration_cancellations_registration_id ON registration_cancellations (registration_id);
CREATE INDEX ix_registration_cancellations_requested_at ON registration_cancellations (requested_at);
CREATE INDEX ix_registration_cancellations_status ON registration_cancellations (status);
CREATE INDEX ix_registration_cancellations_user_id ON registration_cancellations (user_id);
CREATE INDEX ix_registrations_event_id ON registrations (event_id);
CREATE INDEX ix_registrations_room_id ON registrations (room_id);
CREATE INDEX ix_registrations_shift_id ON registrations (shift_id);
CREATE INDEX ix_registrations_status ON registrations (status);
CREATE INDEX ix_registrations_user_id ON registrations (user_id);
CREATE INDEX ix_rooms_hotel_id ON rooms (hotel_id);
CREATE INDEX ix_shifts_event_id ON shifts (event_id);
CREATE INDEX ix_teams_leader_user_id ON teams (leader_user_id);
CREATE INDEX ix_trip_legs_event_id ON trip_legs (event_id);
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE UNIQUE INDEX ix_users_employee_code ON users (employee_code);
CREATE INDEX ix_users_is_active ON users (is_active);
CREATE INDEX ix_users_role ON users (role);
CREATE INDEX ix_users_team_id ON users (team_id);
CREATE UNIQUE INDEX uq_flights_event_code_direction ON flights (event_id, flight_code, direction);
CREATE UNIQUE INDEX uq_gala_seats_assigned_registration ON gala_seats (json_extract(assignment_json, '$.registration_id')) WHERE json_extract(assignment_json, '$.registration_id') IS NOT NULL;
CREATE UNIQUE INDEX uq_registration_cancellations_pending ON registration_cancellations (registration_id) WHERE status = 'pending';
```

## 3. Views (không tính trong số bảng)

Không có VIEW trong revision này.

## 4. Di trú và xác minh

Revision: `c24a29db2026`. Kiểm tra số bảng, archive và foreign key
bằng `backend/scripts/verify_schema_v2.py` trên **bản sao** DB cũ.
Tuyệt đối không dùng `seed_v2.py --reset` trên dữ liệu thật.

## F7 bổ sung: tạm dừng lượt Gala (2026-10-02)

Migration `84e71bc092af` nối tiếp `7d2a9e41c027`, thêm một cột nullable vào schema v2:

```sql
ALTER TABLE gala_layouts ADD COLUMN turn_paused_at VARCHAR(32);
```

`NULL` = lượt chạy bình thường; giá trị UTC ISO là mốc đóng băng cả lượt và hold.
Không thêm bảng hay enum mới. Hạn lượt/hold vẫn nằm ở các cột hiện có. Khi tiếp tục,
service cộng thời gian đã tạm dừng vào các hạn còn được giữ; chuyển/kết thúc lượt xoá
mốc này. Downgrade bị chặn khi có lượt đang pause để tránh làm hết hạn ghế ngoài ý muốn.
