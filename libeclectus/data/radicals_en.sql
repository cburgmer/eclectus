CREATE TABLE RadicalTable_zh_cmn__en (
  RadicalIndex INTEGER NOT NULL,        -- Kangxi radical index
  Reading VARCHAR(255),                 -- Radical name reading
  Meaning TEXT,                         -- Meaning of radical in English
  PRIMARY KEY (RadicalIndex)
);
