-- Create base schema
CREATE TABLE app (
	id INTEGER PRIMARY KEY,
	name TEXT NOT NULL UNIQUE ON CONFLICT FAIL,
	slug TEXT NOT NULL UNIQUE ON CONFLICT FAIL,
	user_id INTEGER NOT NULL,
	description TEXT NOT NULL,
	category_id INTEGER NOT NULL,
	status_id INTEGER NOT NULL,
	download_count INTEGER NOT NULL DEFAULT 0,
	newest_egg_id INTEGER DEFAULT NULL,
	created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE category (
	id INTEGER PRIMARY KEY,
	name TEXT NOT NULL,
	slug TEXT NOT NULL,
	description TEXT NOT NULL
);

CREATE TABLE status (
	id INTEGER PRIMARY KEY,
	name TEXT NOT NULL,
	slug TEXT NOT NULL
);

CREATE TABLE egg (
	id INTEGER PRIMARY KEY,
	app_id INTEGER NOT NULL,
	version INTEGER NOT NULL,
	released BOOLEAN NOT NULL DEFAULT false,
	size INTEGER NOT NULL,
	size_unpacked INTEGER NOT NULL,
	created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
	hash TEXT NOT NULL
);

CREATE TABLE user (
	id INTEGER PRIMARY KEY,
	name TEXT NOT NULL,
	email TEXT NOT NULL,
	password TEXT NOT NULL,
	created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
	updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE egg_file (
	id INTEGER PRIMARY KEY,
	egg_id INTEGER NOT NULL,
	upload_name TEXT NOT NULL,
	local_name TEXT NOT NULL,
	size INTEGER NOT NULL,
	created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
	hash TEXT NOT NULL
);

-- Insert initial data
INSERT INTO category (name, slug, description) VALUES ("Uncategorized", "uncategorized", "Apps that don't fit to any other category");
INSERT INTO category (name, slug, description) VALUES ("Games", "games", "Games!");

INSERT INTO status (name, slug) VALUES ("In Progress", "in_progress");
INSERT INTO status (name, slug) VALUES ("Unusable", "unusable");
INSERT INTO status (name, slug) VALUES ("Working", "working");
