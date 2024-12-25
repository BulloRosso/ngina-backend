CREATE TABLE IF NOT EXISTS "public"."chat_interactions" (
    "id" uuid DEFAULT extensions.uuid_generate_v4() NOT NULL PRIMARY KEY,
    "profile_id" uuid NOT NULL REFERENCES "public"."profiles"("id") ON DELETE CASCADE,
    "timestamp" timestamptz DEFAULT now() NOT NULL,
    "interaction" jsonb NOT NULL,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    "updated_at" timestamptz DEFAULT now() NOT NULL
);

-- Add indexes
CREATE INDEX idx_chat_interactions_profile_id ON "public"."chat_interactions"("profile_id");
CREATE INDEX idx_chat_interactions_timestamp ON "public"."chat_interactions"("timestamp");

-- Enable RLS
ALTER TABLE "public"."chat_interactions" ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT ALL ON TABLE "public"."chat_interactions" TO authenticated;
GRANT ALL ON TABLE "public"."chat_interactions" TO service_role;

CREATE TABLE IF NOT EXISTS "public"."achievement_progress" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "profile_id" "uuid" NOT NULL,
    "achievement_id" "text" NOT NULL,
    "current_count" integer DEFAULT 0,
    "completed" boolean DEFAULT false,
    "unlocked_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."achievement_progress" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."memories" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "profile_id" "uuid" NOT NULL,
    "session_id" "uuid" NOT NULL,
    "category" "text" NOT NULL,
    "description" "text" NOT NULL,
    "time_period" "date" NOT NULL,
    "location" "jsonb",
    "emotions" "text"[] DEFAULT '{}'::"text"[],
    "people" "jsonb"[] DEFAULT '{}'::"jsonb"[],
    "image_urls" "text"[] DEFAULT '{}'::"text"[],
    "audio_url" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "sentiment_analysis" "jsonb"
);


ALTER TABLE "public"."memories" OWNER TO "postgres";

CREATE TABLE IF NOT EXISTS "public"."profiles" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "first_name" "text" NOT NULL,
    "last_name" "text" NOT NULL,
    "date_of_birth" "date" NOT NULL,
    "place_of_birth" "text" NOT NULL,
    "gender" "text" NOT NULL,
    "children" "text"[] DEFAULT '{}'::"text"[],
    "spoken_languages" "text"[] DEFAULT '{}'::"text"[],
    "profile_image_url" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "metadata" "jsonb",
    "subscribed_at" timestamp without time zone,
    "user_id" "uuid"
);


ALTER TABLE "public"."profiles" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."achievement_statistics" AS
 SELECT "p"."id" AS "profile_id",
    "p"."first_name",
    "p"."last_name",
    "count"(DISTINCT "ap"."achievement_id") AS "completed_achievements",
    "count"(DISTINCT "m"."id") AS "total_memories",
    "count"(DISTINCT "m"."id") FILTER (WHERE ("m"."image_urls" <> '{}'::"text"[])) AS "memories_with_photos",
    "count"(DISTINCT "m"."session_id") AS "total_sessions"
   FROM (("public"."profiles" "p"
     LEFT JOIN "public"."achievement_progress" "ap" ON ((("p"."id" = "ap"."profile_id") AND ("ap"."completed" = true))))
     LEFT JOIN "public"."memories" "m" ON (("p"."id" = "m"."profile_id")))
  GROUP BY "p"."id", "p"."first_name", "p"."last_name";


ALTER TABLE "public"."achievement_statistics" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."achievements" (
    "id" "text" NOT NULL,
    "type" "text" NOT NULL,
    "titles" "jsonb" NOT NULL,
    "descriptions" "jsonb" NOT NULL,
    "icon" "text" NOT NULL,
    "color" "text" NOT NULL,
    "required_count" integer NOT NULL,
    "bonus_achievement_id" "text",
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."achievements" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."documents" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "content" "text",
    "metadata" "jsonb",
    "embedding" "extensions"."vector"
);



CREATE TABLE IF NOT EXISTS "public"."interview_invitations" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "profile_id" "uuid",
    "created_by" "uuid",
    "email" "text" NOT NULL,
    "secret_token" "text" NOT NULL,
    "expires_at" timestamp with time zone NOT NULL,
    "last_used_at" timestamp with time zone,
    "status" "text" DEFAULT 'active'::"text" NOT NULL,
    "session_count" integer DEFAULT 0,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."interview_invitations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."interview_sessions" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "profile_id" "uuid" NOT NULL,
    "category" "text" NOT NULL,
    "started_at" timestamp with time zone DEFAULT "now"(),
    "completed_at" timestamp with time zone,
    "summary" "text",
    "emotional_state" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "topics_of_interest" "jsonb" DEFAULT '[]'::"jsonb"
);


ALTER TABLE "public"."interview_sessions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."pdf_exports" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "profile_id" "uuid" NOT NULL,
    "file_url" "text" NOT NULL,
    "generated_at" timestamp with time zone DEFAULT "now"(),
    "category" "text",
    "date_range" "tstzrange",
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."pdf_exports" OWNER TO "postgres";




ALTER TABLE ONLY "public"."achievement_progress"
    ADD CONSTRAINT "achievement_progress_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."achievement_progress"
    ADD CONSTRAINT "achievement_progress_profile_id_achievement_id_key" UNIQUE ("profile_id", "achievement_id");



ALTER TABLE ONLY "public"."achievements"
    ADD CONSTRAINT "achievements_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."documents"
    ADD CONSTRAINT "documents_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."interview_invitations"
    ADD CONSTRAINT "interview_invitations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."interview_invitations"
    ADD CONSTRAINT "interview_invitations_secret_token_key" UNIQUE ("secret_token");



ALTER TABLE ONLY "public"."interview_sessions"
    ADD CONSTRAINT "interview_sessions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."memories"
    ADD CONSTRAINT "memories_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."pdf_exports"
    ADD CONSTRAINT "pdf_exports_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."profiles"
    ADD CONSTRAINT "profiles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_email_key" UNIQUE ("email");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");



CREATE INDEX "idx_achievement_progress_profile" ON "public"."achievement_progress" USING "btree" ("profile_id");



CREATE INDEX "idx_interview_sessions_topics" ON "public"."interview_sessions" USING "gin" ("topics_of_interest");



CREATE INDEX "idx_invitations_email" ON "public"."interview_invitations" USING "btree" ("email");



CREATE INDEX "idx_invitations_profile" ON "public"."interview_invitations" USING "btree" ("profile_id");



CREATE INDEX "idx_invitations_token" ON "public"."interview_invitations" USING "btree" ("secret_token");



CREATE INDEX "idx_memories_profile_id" ON "public"."memories" USING "btree" ("profile_id");



CREATE INDEX "idx_memories_profile_timeline" ON "public"."memories" USING "btree" ("profile_id", "time_period" DESC);



CREATE INDEX "idx_memories_session_id" ON "public"."memories" USING "btree" ("session_id");



CREATE INDEX "idx_memories_time_period" ON "public"."memories" USING "btree" ("time_period");



CREATE INDEX "idx_profiles_user_id" ON "public"."profiles" USING "btree" ("user_id");



CREATE INDEX "idx_sessions_profile_id" ON "public"."interview_sessions" USING "btree" ("profile_id");



CREATE INDEX "idx_users_email" ON "public"."users" USING "btree" ("email");



CREATE OR REPLACE TRIGGER "achievement_progress_updated_at" BEFORE UPDATE ON "public"."achievement_progress" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at"();



CREATE OR REPLACE TRIGGER "interview_invitations_updated_at" BEFORE UPDATE ON "public"."interview_invitations" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at"();



CREATE OR REPLACE TRIGGER "memories_updated_at" BEFORE UPDATE ON "public"."memories" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at"();



CREATE OR REPLACE TRIGGER "profiles_updated_at" BEFORE UPDATE ON "public"."profiles" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at"();



CREATE OR REPLACE TRIGGER "sessions_updated_at" BEFORE UPDATE ON "public"."interview_sessions" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at"();




ALTER TABLE ONLY "public"."achievement_progress"
    ADD CONSTRAINT "achievement_progress_achievement_id_fkey" FOREIGN KEY ("achievement_id") REFERENCES "public"."achievements"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."achievement_progress"
    ADD CONSTRAINT "achievement_progress_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "public"."profiles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."achievements"
    ADD CONSTRAINT "achievements_bonus_achievement_id_fkey" FOREIGN KEY ("bonus_achievement_id") REFERENCES "public"."achievements"("id");



ALTER TABLE ONLY "public"."profiles"
    ADD CONSTRAINT "fk_user" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."interview_invitations"
    ADD CONSTRAINT "interview_invitations_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."interview_invitations"
    ADD CONSTRAINT "interview_invitations_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "public"."profiles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."interview_sessions"
    ADD CONSTRAINT "interview_sessions_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "public"."profiles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."memories"
    ADD CONSTRAINT "memories_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "public"."profiles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."memories"
    ADD CONSTRAINT "memories_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."interview_sessions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."memory_sentiments"
    ADD CONSTRAINT "memory_sentiments_memory_id_fkey" FOREIGN KEY ("memory_id") REFERENCES "public"."memories"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."pdf_exports"
    ADD CONSTRAINT "pdf_exports_profile_id_fkey" FOREIGN KEY ("profile_id") REFERENCES "public"."profiles"("id") ON DELETE CASCADE;



CREATE POLICY "Admin service API only" ON "public"."users" USING ((("auth"."jwt"() ->> 'role'::"text") = 'service_role'::"text"));



ALTER TABLE "public"."achievement_progress" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."documents" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."interview_sessions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."memories" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."pdf_exports" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."profiles" ENABLE ROW LEVEL SECURITY;














































































































































































































































































































































































































































































































































GRANT ALL ON FUNCTION "public"."update_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_updated_at"() TO "service_role";






























GRANT ALL ON TABLE "public"."achievement_progress" TO "anon";
GRANT ALL ON TABLE "public"."achievement_progress" TO "authenticated";
GRANT ALL ON TABLE "public"."achievement_progress" TO "service_role";



GRANT ALL ON TABLE "public"."memories" TO "anon";
GRANT ALL ON TABLE "public"."memories" TO "authenticated";
GRANT ALL ON TABLE "public"."memories" TO "service_role";



GRANT ALL ON TABLE "public"."profiles" TO "anon";
GRANT ALL ON TABLE "public"."profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."profiles" TO "service_role";



GRANT ALL ON TABLE "public"."achievement_statistics" TO "anon";
GRANT ALL ON TABLE "public"."achievement_statistics" TO "authenticated";
GRANT ALL ON TABLE "public"."achievement_statistics" TO "service_role";



GRANT ALL ON TABLE "public"."achievements" TO "anon";
GRANT ALL ON TABLE "public"."achievements" TO "authenticated";
GRANT ALL ON TABLE "public"."achievements" TO "service_role";



GRANT ALL ON TABLE "public"."documents" TO "anon";
GRANT ALL ON TABLE "public"."documents" TO "authenticated";
GRANT ALL ON TABLE "public"."documents" TO "service_role";



GRANT ALL ON SEQUENCE "public"."documents_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."documents_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."documents_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."interview_invitations" TO "anon";
GRANT ALL ON TABLE "public"."interview_invitations" TO "authenticated";
GRANT ALL ON TABLE "public"."interview_invitations" TO "service_role";



GRANT ALL ON TABLE "public"."interview_sessions" TO "anon";
GRANT ALL ON TABLE "public"."interview_sessions" TO "authenticated";
GRANT ALL ON TABLE "public"."interview_sessions" TO "service_role";



GRANT ALL ON TABLE "public"."memory_sentiments" TO "anon";
GRANT ALL ON TABLE "public"."memory_sentiments" TO "authenticated";
GRANT ALL ON TABLE "public"."memory_sentiments" TO "service_role";



GRANT ALL ON TABLE "public"."pdf_exports" TO "anon";
GRANT ALL ON TABLE "public"."pdf_exports" TO "authenticated";
GRANT ALL ON TABLE "public"."pdf_exports" TO "service_role";



GRANT ALL ON TABLE "public"."users" TO "anon";
GRANT ALL ON TABLE "public"."users" TO "authenticated";
GRANT ALL ON TABLE "public"."users" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "service_role";






























RESET ALL;
