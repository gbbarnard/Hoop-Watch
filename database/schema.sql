-- database/schema.sql
-- Hoop Watch / NBA Jam PR2 schema
-- MySQL 8+ recommended

DROP DATABASE IF EXISTS hoopwatch;
CREATE DATABASE hoopwatch CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE hoopwatch;

-- ---------- USERS ----------
CREATE TABLE users (
  user_id           INT AUTO_INCREMENT PRIMARY KEY,
  email             VARCHAR(255) NULL UNIQUE,
  username          VARCHAR(80) NULL UNIQUE,
  display_name      VARCHAR(120) NULL,
  bio               TEXT NULL,
  profile_image_url VARCHAR(500) NULL,
  password_hash     VARCHAR(255) NULL,
  role              ENUM('base','pro','admin') NOT NULL DEFAULT 'base',
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


CREATE TABLE teams (
  team_id       INT AUTO_INCREMENT PRIMARY KEY,
  nba_team_id   VARCHAR(32) NULL UNIQUE,
  name          VARCHAR(120) NOT NULL,
  abbreviation  VARCHAR(10) NOT NULL UNIQUE,
  conference    ENUM('East','West') NOT NULL,
  logo_url      VARCHAR(500) NULL,
  city          VARCHAR(80) NOT NULL,
  state         VARCHAR(40) NULL,
  country       VARCHAR(60) NOT NULL DEFAULT 'USA',
  arena_name    VARCHAR(120) NULL
) ENGINE=InnoDB;

-- ---------- PLAYERS ----------
CREATE TABLE players (
  player_id      INT AUTO_INCREMENT PRIMARY KEY,
  nba_player_id  VARCHAR(32) NULL UNIQUE,  -- for later API mapping
  team_id        INT NULL,
  first_name     VARCHAR(60) NOT NULL,
  last_name      VARCHAR(60) NOT NULL,
  position       ENUM('PG','SG','SF','PF','C','G','F') NULL,
  jersey_number  INT NULL,
  height_in      INT NULL,
  weight_lb      INT NULL,
  birth_date     DATE NULL,
  headshot_url   VARCHAR(500) NULL,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT fk_players_team
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  INDEX idx_players_team (team_id),
  INDEX idx_players_name (last_name, first_name)
) ENGINE=InnoDB;

-- ---------- TEAM STANDINGS ----------
CREATE TABLE team_standings (
  team_id     INT PRIMARY KEY,
  wins        INT NOT NULL DEFAULT 0,
  losses      INT NOT NULL DEFAULT 0,
  last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_standings_team
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------- GAMES + CACHE ----------
CREATE TABLE games (
  game_id        INT AUTO_INCREMENT PRIMARY KEY,
  nba_game_id    VARCHAR(32) NULL UNIQUE,  -- for later API mapping
  home_team_id   INT NOT NULL,
  away_team_id   INT NOT NULL,
  game_date      DATE NOT NULL,
  start_time     TIME NULL,
  status         ENUM('scheduled','live','final') NOT NULL DEFAULT 'scheduled',
  CONSTRAINT fk_games_home
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_games_away
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  INDEX idx_games_date (game_date),
  INDEX idx_games_home (home_team_id),
  INDEX idx_games_away (away_team_id)
) ENGINE=InnoDB;

CREATE TABLE game_cache (
  game_id      INT PRIMARY KEY,
  home_score   INT NOT NULL DEFAULT 0,
  away_score   INT NOT NULL DEFAULT 0,
  period       INT NULL,
  clock        VARCHAR(20) NULL,
  fetched_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at   TIMESTAMP NULL,
  CONSTRAINT fk_cache_game
    FOREIGN KEY (game_id) REFERENCES games(game_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------- FAVORITES + WATCHLIST ----------
CREATE TABLE favorites (
  favorite_id  INT AUTO_INCREMENT PRIMARY KEY,
  user_id      INT NOT NULL,
  team_id      INT NOT NULL,
  created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_favorites_user
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_favorites_team
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  UNIQUE KEY uq_favorites (user_id, team_id),
  INDEX idx_fav_user (user_id)
) ENGINE=InnoDB;

CREATE TABLE watchlist (
  watch_id    INT AUTO_INCREMENT PRIMARY KEY,
  user_id     INT NOT NULL,
  game_id     INT NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_watch_user
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_watch_game
    FOREIGN KEY (game_id) REFERENCES games(game_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  UNIQUE KEY uq_watchlist (user_id, game_id)
) ENGINE=InnoDB;

-- ---------- ALERT RULES ----------
CREATE TABLE alert_rules (
  alert_rule_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NOT NULL,
  game_id       INT NULL,
  team_id       INT NULL,
  rule_type     ENUM('game_start') NOT NULL DEFAULT 'game_start',
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_alert_user
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_alert_game
    FOREIGN KEY (game_id) REFERENCES games(game_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_alert_team
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------- HOME PAGE CONTENT ----------
CREATE TABLE daily_content (
  content_date   DATE PRIMARY KEY,
  fact_text      VARCHAR(500) NOT NULL,
  featured_game_id INT NULL,
  admin_user_id  INT NOT NULL,
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_daily_admin
    FOREIGN KEY (admin_user_id) REFERENCES users(user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_daily_featured_game
    FOREIGN KEY (featured_game_id) REFERENCES games(game_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE teams_to_watch (
  tw_id        INT AUTO_INCREMENT PRIMARY KEY,
  watch_date   DATE NOT NULL,
  team_id      INT NOT NULL,
  admin_user_id INT NOT NULL,
  UNIQUE KEY uq_tw (watch_date, team_id),
  CONSTRAINT fk_tw_team
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_tw_admin
    FOREIGN KEY (admin_user_id) REFERENCES users(user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------- QOTD ----------
CREATE TABLE qotd_questions (
  question_id   INT AUTO_INCREMENT PRIMARY KEY,
  admin_user_id INT NOT NULL,
  question_date DATE NOT NULL UNIQUE,
  question_text VARCHAR(300) NOT NULL,
  is_open       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_qotd_admin
    FOREIGN KEY (admin_user_id) REFERENCES users(user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE qotd_comments (
  comment_id        INT AUTO_INCREMENT PRIMARY KEY,
  question_id       INT NOT NULL,
  user_id           INT NOT NULL,
  parent_comment_id INT NULL,
  comment_text      VARCHAR(500) NOT NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_qc_question
    FOREIGN KEY (question_id) REFERENCES qotd_questions(question_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_qc_user
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_qc_parent
    FOREIGN KEY (parent_comment_id) REFERENCES qotd_comments(comment_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  INDEX idx_qc_question (question_id),
  INDEX idx_qc_parent (parent_comment_id)
) ENGINE=InnoDB;

CREATE TABLE qotd_comment_votes (
  comment_id INT NOT NULL,
  user_id    INT NOT NULL,
  vote_value TINYINT NOT NULL, -- -1 or +1
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (comment_id, user_id),
  CONSTRAINT fk_qv_comment
    FOREIGN KEY (comment_id) REFERENCES qotd_comments(comment_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_qv_user
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------- GAME COMMENTS ----------
CREATE TABLE game_comments (
  comment_id        INT AUTO_INCREMENT PRIMARY KEY,
  user_id           INT NOT NULL,
  game_id           INT NOT NULL,
  parent_comment_id INT NULL,
  comment_text      VARCHAR(500) NOT NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_gc_user
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_gc_game
    FOREIGN KEY (game_id) REFERENCES games(game_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_gc_parent
    FOREIGN KEY (parent_comment_id) REFERENCES game_comments(comment_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  INDEX idx_gc_game (game_id),
  INDEX idx_gc_parent (parent_comment_id)
) ENGINE=InnoDB;
