CREATE TABLE EduTwIndex (
  ChineseCharacter CHAR(1) NOT NULL,        -- Character
  CharValue VARCHAR(255) NOT NULL,          -- Link to stroke order page
  PRIMARY KEY (ChineseCharacter)
);