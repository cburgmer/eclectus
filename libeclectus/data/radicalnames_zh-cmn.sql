CREATE TABLE RadicalNames_zh_cmn (
  RadicalIndex INTEGER NOT NULL,            -- Kangxi radical index
  Type  CHAR DEFAULT NULL,
  TraditionalName VARCHAR(10) NOT NULL,     -- Radical name in trad. Chinese
  SimplifiedName VARCHAR(10) NOT NULL,      -- Radical name in simp. Chinese
  TraditionalShortName VARCHAR(1) NOT NULL, -- Radical short trad. identifier
  SimplifiedShortName VARCHAR(1) NOT NULL,  -- Radical short simp. identifier
  Reading VARCHAR(100) NOT NULL,            -- Radical name reading
  PRIMARY KEY (RadicalIndex, Type, TraditionalName)
);
