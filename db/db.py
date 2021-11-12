#!/usr/bin/python3

import psycopg2

conn = None
curs = None

createReplaceTrigger = """CREATE OR REPLACE FUNCTION record_unique_host() RETURNS TRIGGER AS $record_host$
                BEGIN
                    --
                    -- Copy host_name and date from main_jobhostsummary to unique_host
                    -- if not already present
                    --
                    IF (TG_OP = 'INSERT') THEN
                        INSERT INTO unique_host (host_name, executed)
                        VALUES (NEW.host_name, NEW.created)
                        ON CONFLICT DO NOTHING;
                    END IF;
                    RETURN NULL;
                END;
            $record_host$ LANGUAGE plpgsql;

            CREATE TRIGGER record_host
            AFTER INSERT OR UPDATE ON main_jobhostsummary
                FOR EACH ROW EXECUTE FUNCTION record_unique_host();"""

# Drops both the function and the trigger
dropTrigger = """DROP FUNCTION record_unique_host CASCADE;"""

def installHostHistoryTrigger():
    getCursor().execute(createReplaceTrigger)
    conn.commit()

def removeHostHistoryTrigger():
    getCursor().execute(dropTrigger)
    conn.commit()

def login(dbName, dbUser, dbPass, dbHost, dbPort):
    global conn
    conn = psycopg2.connect(database=dbName, user=dbUser, password = dbPass, host=dbHost, port=dbPort)

def getCursor():
    global curs
    if conn is None:
        print("Please log into DB!")
    elif curs is None:
        curs = conn.cursor()
    return curs

def getNewHosts():
    getCursor().execute("SELECT * FROM unique_host WHERE billed_date IS NULL")
    hosts = getCursor().fetchall()
    return hosts

def markHostsBilled(hosts):
    query = "UPDATE unique_host SET billed_date = current_timestamp WHERE host_name = '%s'"
    for host in hosts:
        (name, _, _) = host
        getCursor().execute(query % name)
    conn.commit()
