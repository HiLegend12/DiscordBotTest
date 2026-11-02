CREATE TABLE IF NOT EXISTS user_info (
    user_id       BIGINT  NOT NULL,
    xp            INT     NOT NULL DEFAULT 0,
    level         INT     NOT NULL DEFAULT 0,
    last_message  DOUBLE  NOT NULL DEFAULT 0,
    last_daily    DOUBLE  NOT NULL DEFAULT 0,
    daily_streak  INT     NOT NULL DEFAULT 0,
    coins         BIGINT  NOT NULL DEFAULT 0,
    last_mine     DOUBLE  NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS inventory (
    user_id   BIGINT      NOT NULL,
    item      VARCHAR(32) NOT NULL,
    quantity  INT         NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, item)
);