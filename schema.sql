CREATE TABLE IF NOT EXISTS user_info (
    user_id       BIGINT      NOT NULL,
    xp            INT         NOT NULL DEFAULT 0,
    level         INT         NOT NULL DEFAULT 0,
    last_message  DOUBLE      NOT NULL DEFAULT 0,
    last_daily    DOUBLE      NOT NULL DEFAULT 0,
    daily_streak  INT         NOT NULL DEFAULT 0,
    coins         BIGINT      NOT NULL DEFAULT 0,
    last_mine     DOUBLE      NOT NULL DEFAULT 0,
    pickaxe       VARCHAR(32) NOT NULL DEFAULT 'hand',
    mining_xp     INT         NOT NULL DEFAULT 0,
    mining_level  INT         NOT NULL DEFAULT 0,
    forge_count   INT         NOT NULL DEFAULT 0,
    forge_size    INT         NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS inventory (
    user_id   BIGINT      NOT NULL,
    item      VARCHAR(32) NOT NULL,
    quantity  INT         NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, item)
);

CREATE TABLE IF NOT EXISTS smelting (
    user_id      BIGINT      NOT NULL,
    slot         INT         NOT NULL,
    bar          VARCHAR(32) NOT NULL,
    amount       INT         NOT NULL,
    finish_time  DOUBLE      NOT NULL,
    PRIMARY KEY (user_id, slot)
);