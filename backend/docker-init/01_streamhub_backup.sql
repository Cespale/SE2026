--
-- PostgreSQL database dump
--


-- Dumped from database version 16.14 (Debian 16.14-1.pgdg13+1)
-- Dumped by pg_dump version 16.14 (Debian 16.14-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: categories; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.categories (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    type smallint,
    sort_order integer
);


ALTER TABLE public.categories OWNER TO postgres;

--
-- Name: categories_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.categories_id_seq OWNER TO postgres;

--
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
-- Name: comments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.comments (
    id uuid NOT NULL,
    content text NOT NULL,
    user_id uuid,
    video_id uuid,
    parent_id uuid,
    reply_to_user_id uuid,
    like_count integer,
    is_top boolean,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.comments OWNER TO postgres;

--
-- Name: danmaku; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.danmaku (
    id uuid NOT NULL,
    content text NOT NULL,
    color character varying(20),
    "position" smallint,
    user_id uuid,
    target_id uuid NOT NULL,
    target_type smallint,
    video_time integer,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.danmaku OWNER TO postgres;

--
-- Name: live_rooms; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.live_rooms (
    id uuid NOT NULL,
    title character varying(120) NOT NULL,
    description text,
    category_id integer,
    cover text,
    stream_key character varying(80) NOT NULL,
    push_url text,
    pull_url text,
    anchor_id uuid,
    online_count integer,
    start_time timestamp with time zone DEFAULT now(),
    end_time timestamp with time zone,
    status smallint,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.live_rooms OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    account character varying(50) NOT NULL,
    password_hash character varying(255) NOT NULL,
    nickname character varying(50) NOT NULL,
    avatar text,
    bio text,
    user_type smallint,
    status smallint,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    stream_key character varying(20)
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: videos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.videos (
    id uuid NOT NULL,
    title character varying(120) NOT NULL,
    description text,
    tags character varying[],
    cover_url text,
    video_url text,
    duration integer,
    category_id integer,
    view_count integer,
    like_count integer,
    comment_count integer,
    favorite_count integer,
    uploader_id uuid,
    audit_status smallint,
    status smallint,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    reject_reason text
);


ALTER TABLE public.videos OWNER TO postgres;

--
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- Data for Name: categories; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.categories (id, name, type, sort_order) FROM stdin;
1	推荐	0	1
2	影视	0	2
3	动画	0	3
4	科技	0	4
5	学习	0	5
6	生活	0	6
7	音乐	0	7
8	游戏	0	8
9	旅行	0	9
10	直播	1	10
\.


--
-- Data for Name: comments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.comments (id, content, user_id, video_id, parent_id, like_count, is_top, created_at) FROM stdin;
2f0045c3-d426-460b-b1f5-3c96bd150db3	这个视频可以正常播放，画质也很清楚！	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	a2f9e923-519d-496c-bad5-8c535d9a63e7	\N	18	f	2026-05-23 11:29:16.144721+00
d375f9da-61c7-4bed-a2e7-9fe6a0dd5129	这个页面已经有评论功能了，刷新后评论也会保留。	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	a2f9e923-519d-496c-bad5-8c535d9a63e7	\N	9	f	2026-05-23 11:29:16.144721+00
7dbc8d96-f8fd-4ff1-89be-5dcdc5437f19	弹幕和评论一起出现，感觉更像真实的视频平台。	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	a2f9e923-519d-496c-bad5-8c535d9a63e7	\N	12	f	2026-05-23 11:29:16.144721+00
78b8d279-e106-4c1f-b03e-33ac67f5e0e4	这个视频可以正常播放，画质也很清楚！	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	41213795-4d63-4dfd-9b0f-9aa702ec02f6	\N	18	f	2026-05-23 11:29:16.144721+00
5b2d773d-888f-4477-8d09-0f375420569a	这个页面已经有评论功能了，刷新后评论也会保留。	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	41213795-4d63-4dfd-9b0f-9aa702ec02f6	\N	9	f	2026-05-23 11:29:16.144721+00
58120ba2-252b-4c8e-8ab1-a863c0fea59c	弹幕和评论一起出现，感觉更像真实的视频平台。	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	41213795-4d63-4dfd-9b0f-9aa702ec02f6	\N	12	f	2026-05-23 11:29:16.144721+00
542a154a-aed3-4eba-8dbb-757959366c0c	这个视频可以正常播放，画质也很清楚！	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	31b49f5b-cdc9-4381-80e0-4548478a0792	\N	18	f	2026-05-23 11:29:16.144721+00
84cab928-3763-4dc6-a90f-4cc239d0ae7b	这个页面已经有评论功能了，刷新后评论也会保留。	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	31b49f5b-cdc9-4381-80e0-4548478a0792	\N	9	f	2026-05-23 11:29:16.144721+00
d6ef98e3-c03d-477e-bae3-d8740598b5d7	弹幕和评论一起出现，感觉更像真实的视频平台。	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	31b49f5b-cdc9-4381-80e0-4548478a0792	\N	12	f	2026-05-23 11:29:16.144721+00
1d5abb3c-9201-401a-adaa-b23e16698e77	这个视频可以正常播放，画质也很清楚！	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	e1d79958-5e96-4f19-ad51-7e2c956fb6e2	\N	18	f	2026-05-23 11:29:16.144721+00
3bdcccc6-9533-48c5-8d56-4cceb0f8bc54	这个页面已经有评论功能了，刷新后评论也会保留。	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	e1d79958-5e96-4f19-ad51-7e2c956fb6e2	\N	9	f	2026-05-23 11:29:16.144721+00
d8e796a1-b0a5-4021-a5f9-7cea604c3d29	弹幕和评论一起出现，感觉更像真实的视频平台。	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	e1d79958-5e96-4f19-ad51-7e2c956fb6e2	\N	12	f	2026-05-23 11:29:16.144721+00
e32bac46-33c1-46ec-9ee0-99b4b1c574be	这个视频可以正常播放，画质也很清楚！	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	76afaacb-d03f-45bf-9c79-00c948dcc883	\N	18	f	2026-05-23 11:29:16.144721+00
5a9001e7-6cae-4127-b9fa-d6da33ea7e5f	这个页面已经有评论功能了，刷新后评论也会保留。	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	76afaacb-d03f-45bf-9c79-00c948dcc883	\N	9	f	2026-05-23 11:29:16.144721+00
6cb88903-50a8-46ac-9f92-f68bde9a2dad	弹幕和评论一起出现，感觉更像真实的视频平台。	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	76afaacb-d03f-45bf-9c79-00c948dcc883	\N	12	f	2026-05-23 11:29:16.144721+00
44d11630-ca3a-4c8d-92e8-e0ecfcaf9d9c	这个视频可以正常播放，画质也很清楚！	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	b596beb7-7c06-4877-9dcd-5dc5c4df8ef2	\N	18	f	2026-05-23 11:29:16.144721+00
7ebad371-e352-4567-bde1-13e71d1da9f7	这个页面已经有评论功能了，刷新后评论也会保留。	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	b596beb7-7c06-4877-9dcd-5dc5c4df8ef2	\N	9	f	2026-05-23 11:29:16.144721+00
6abee364-8f01-49f4-9185-6d31f4564163	弹幕和评论一起出现，感觉更像真实的视频平台。	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	b596beb7-7c06-4877-9dcd-5dc5c4df8ef2	\N	12	f	2026-05-23 11:29:16.144721+00
\.


--
-- Data for Name: danmaku; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.danmaku (id, content, color, "position", user_id, target_id, target_type, video_time, created_at) FROM stdin;
f1b21c65-c025-4e89-8e68-6dd72cb6920e	来了来了！	#ffffff	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	a2f9e923-519d-496c-bad5-8c535d9a63e7	0	2	2026-05-23 11:29:16.191467+00
5687f38b-dcf1-476f-88ba-c8bf2c53d6c3	这个视频终于能播放了	#ff4d4f	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	a2f9e923-519d-496c-bad5-8c535d9a63e7	0	5	2026-05-23 11:29:16.191467+00
5aa7deae-75e8-4e94-81ea-c3f61a007448	作业展示效果不错	#00d4ff	0	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	a2f9e923-519d-496c-bad5-8c535d9a63e7	0	8	2026-05-23 11:29:16.191467+00
f52a6453-9739-4d29-8a5d-f54050c76602	前端 + 后端 + 数据库已经打通	#fadb14	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	a2f9e923-519d-496c-bad5-8c535d9a63e7	0	12	2026-05-23 11:29:16.191467+00
b5b665c7-7b0a-4168-8699-3a74567bd675	来了来了！	#ffffff	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	41213795-4d63-4dfd-9b0f-9aa702ec02f6	0	2	2026-05-23 11:29:16.191467+00
98d4a7ae-edcb-42e6-98b8-ce99f61cf0a7	这个视频终于能播放了	#ff4d4f	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	41213795-4d63-4dfd-9b0f-9aa702ec02f6	0	5	2026-05-23 11:29:16.191467+00
2d96476d-c43f-436c-95a8-8f30c1c5f8c4	作业展示效果不错	#00d4ff	0	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	41213795-4d63-4dfd-9b0f-9aa702ec02f6	0	8	2026-05-23 11:29:16.191467+00
6d4b33b6-e585-4d8c-b95d-827758f001ac	前端 + 后端 + 数据库已经打通	#fadb14	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	41213795-4d63-4dfd-9b0f-9aa702ec02f6	0	12	2026-05-23 11:29:16.191467+00
cf0a5e57-a995-4603-9c8f-bdeb465f05b2	来了来了！	#ffffff	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	31b49f5b-cdc9-4381-80e0-4548478a0792	0	2	2026-05-23 11:29:16.191467+00
ec5afb29-d0c1-4c26-bb5b-bc1d3683438f	这个视频终于能播放了	#ff4d4f	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	31b49f5b-cdc9-4381-80e0-4548478a0792	0	5	2026-05-23 11:29:16.191467+00
50f28f6f-8429-4d71-b2ee-0986eda14774	作业展示效果不错	#00d4ff	0	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	31b49f5b-cdc9-4381-80e0-4548478a0792	0	8	2026-05-23 11:29:16.191467+00
f6fbe7fb-8c51-42cd-b9e4-0729a2944811	前端 + 后端 + 数据库已经打通	#fadb14	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	31b49f5b-cdc9-4381-80e0-4548478a0792	0	12	2026-05-23 11:29:16.191467+00
7e4f592f-bd52-4acb-99e7-5cd4bd942616	来了来了！	#ffffff	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	e1d79958-5e96-4f19-ad51-7e2c956fb6e2	0	2	2026-05-23 11:29:16.191467+00
a7e5eddf-d516-46e9-98d7-539197ab81cf	这个视频终于能播放了	#ff4d4f	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	e1d79958-5e96-4f19-ad51-7e2c956fb6e2	0	5	2026-05-23 11:29:16.191467+00
876e8cab-c731-4057-b698-ca557227fc93	作业展示效果不错	#00d4ff	0	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	e1d79958-5e96-4f19-ad51-7e2c956fb6e2	0	8	2026-05-23 11:29:16.191467+00
09ef2de5-5180-4d17-939c-01ebfed0196d	前端 + 后端 + 数据库已经打通	#fadb14	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	e1d79958-5e96-4f19-ad51-7e2c956fb6e2	0	12	2026-05-23 11:29:16.191467+00
9b715314-eccb-407a-ae6f-4fbfa8c760ee	来了来了！	#ffffff	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	76afaacb-d03f-45bf-9c79-00c948dcc883	0	2	2026-05-23 11:29:16.191467+00
2ad28227-e183-4e04-885a-629108664a21	这个视频终于能播放了	#ff4d4f	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	76afaacb-d03f-45bf-9c79-00c948dcc883	0	5	2026-05-23 11:29:16.191467+00
ecb40c6b-c1d3-4245-beb4-68deb2d974de	作业展示效果不错	#00d4ff	0	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	76afaacb-d03f-45bf-9c79-00c948dcc883	0	8	2026-05-23 11:29:16.191467+00
4ec10864-955f-4a60-ada1-c22c8a1eb293	前端 + 后端 + 数据库已经打通	#fadb14	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	76afaacb-d03f-45bf-9c79-00c948dcc883	0	12	2026-05-23 11:29:16.191467+00
447580bf-c48b-4768-846e-210417bddff1	来了来了！	#ffffff	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	b596beb7-7c06-4877-9dcd-5dc5c4df8ef2	0	2	2026-05-23 11:29:16.191467+00
4fe1fc3e-aee4-44c8-9543-b61b014c7b0e	这个视频终于能播放了	#ff4d4f	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	b596beb7-7c06-4877-9dcd-5dc5c4df8ef2	0	5	2026-05-23 11:29:16.191467+00
cebff8d2-69bd-40a1-9bb1-deeaa3e7a65d	作业展示效果不错	#00d4ff	0	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	b596beb7-7c06-4877-9dcd-5dc5c4df8ef2	0	8	2026-05-23 11:29:16.191467+00
8c9f81d8-3e55-459e-86b2-16cfbbeabfe8	前端 + 后端 + 数据库已经打通	#fadb14	0	1cbeeb55-ed92-49f9-9d89-1554ae643a4b	b596beb7-7c06-4877-9dcd-5dc5c4df8ef2	0	12	2026-05-23 11:29:16.191467+00
\.


--
-- Data for Name: live_rooms; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.live_rooms (id, title, category_id, cover, stream_key, push_url, pull_url, anchor_id, online_count, start_time, end_time, status, created_at) FROM stdin;
fafc3192-ad80-4675-8d9c-20c054f04881	学习区直播：软件工程项目答疑	10	https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=900&auto=format&fit=crop	stream_demo_001	rtmp://localhost/live/stream_demo_001	http://localhost:8080/live/stream_demo_001.flv	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	128	2026-05-23 11:29:16.242505+00	\N	1	2026-05-23 11:29:16.242505+00
e9218c7e-8639-4278-9750-679f8072ccbd	生活区直播：今晚一起剪视频	10	https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=900&auto=format&fit=crop	stream_demo_002	rtmp://localhost/live/stream_demo_002	http://localhost:8080/live/stream_demo_002.flv	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	86	2026-05-23 11:29:16.242505+00	\N	1	2026-05-23 11:29:16.242505+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, account, password_hash, nickname, avatar, bio, user_type, status, created_at, updated_at) FROM stdin;
8a69bb66-f64a-4a44-9e2a-1ec4f69cceba	admin	$2b$12$4XZBgsUdh/NzrWsBIOK4Ueo8OWuVnSvvMebmDA3jQeQasIBTADGeq	管理员	https://api.dicebear.com/7.x/avataaars/svg?seed=admin	平台管理员，负责视频审核与社区管理	2	0	2026-05-23 11:29:14.505022+00	2026-05-23 11:29:14.505022+00
3931ea83-5e99-47d3-a38b-ba96e9ed59e2	creator	$2b$12$tj11Slv42ummnuJFG/.HQOUc4GbvpXYCTxIqQ97CLQOg55y1Kw8lC	创作者小明	https://api.dicebear.com/7.x/avataaars/svg?seed=creator	热爱拍摄、剪辑和分享生活的内容创作者	1	0	2026-05-23 11:29:14.505022+00	2026-05-23 11:29:14.505022+00
1cbeeb55-ed92-49f9-9d89-1554ae643a4b	user	$2b$12$CXcSiYdpwZTdfZ7Y0.VNQeBcw08RAyIgtwcytxrfnHAygnRNuTyC.	xuyue	https://api.dicebear.com/7.x/avataaars/svg?seed=user	喜欢看视频、发弹幕和评论的普通用户	0	0	2026-05-23 11:29:14.505022+00	2026-05-23 11:29:14.505022+00
\.


--
-- Data for Name: videos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.videos (id, title, description, tags, cover_url, video_url, duration, category_id, view_count, like_count, comment_count, favorite_count, uploader_id, audit_status, status, created_at, updated_at) FROM stdin;
a2f9e923-519d-496c-bad5-8c535d9a63e7	Big Buck Bunny 动画短片	一部经典开源动画短片，适合用于测试在线视频播放功能。	{动画,短片,开源影片}	https://peach.blender.org/wp-content/uploads/title_anouncement.jpg?x11217	https://storage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4	596	3	12800	860	3	320	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	1	2026-05-23 11:29:16.028352+00	2026-05-23 11:29:16.268248+00
41213795-4d63-4dfd-9b0f-9aa702ec02f6	Sintel 电影宣传片	Blender Foundation 开源电影 Sintel，用于展示高清影视播放效果。	{电影,宣传片,高清}	https://download.blender.org/durian/trailer/sintel_trailer-480p.jpg	https://storage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4	888	2	9360	742	3	226	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	1	2026-05-23 11:29:16.052536+00	2026-05-23 11:29:16.268248+00
31b49f5b-cdc9-4381-80e0-4548478a0792	Tears of Steel 科幻短片	一部科幻风格开源短片，可用于展示中长视频播放页面。	{科幻,电影,短片}	https://mango.blender.org/wp-content/uploads/2013/05/01_thom_celia_bridge.jpg	https://storage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4	734	2	8420	611	3	188	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	1	2026-05-23 11:29:16.070591+00	2026-05-23 11:29:16.268248+00
e1d79958-5e96-4f19-ad51-7e2c956fb6e2	Elephants Dream 开源动画	经典实验动画短片，适合展示平台推荐和播放功能。	{动画,实验短片,创意}	https://orange.blender.org/wp-content/themes/orange/images/media/gallery/s1_proog.jpg	https://storage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4	653	3	7340	520	3	176	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	1	2026-05-23 11:29:16.084676+00	2026-05-23 11:29:16.268248+00
76afaacb-d03f-45bf-9c79-00c948dcc883	For Bigger Blazes 宣传片	Google 官方示例视频，适合测试网页播放器兼容性。	{宣传片,科技,短视频}	https://images.unsplash.com/photo-1485846234645-a62644f84728?w=900&auto=format&fit=crop	https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4	15	4	5620	410	3	105	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	1	2026-05-23 11:29:16.101982+00	2026-05-23 11:29:16.268248+00
b596beb7-7c06-4877-9dcd-5dc5c4df8ef2	For Bigger Escape 宣传片	短视频宣传片素材，适合用于测试短视频与推荐列表。	{短视频,生活,宣传片}	https://images.unsplash.com/photo-1492691527719-9d1e07e534b4?w=900&auto=format&fit=crop	https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4	15	6	4890	366	3	98	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	1	2026-05-23 11:29:16.117072+00	2026-05-23 11:29:16.268248+00
1b464c00-f0f9-47ac-ba40-500d47349bb4	4K Abstract Sci Fi Tunnel Vj Motion Background    Neon Light Tunnel Free Vj Loops    4K Vj Loops	这是系统自动从 public/demo-videos 目录读取的视频文件：4K Abstract Sci-Fi Tunnel VJ Motion Background __ Neon Light Tunnel Free VJ Loops __ 4K VJ Loops.mp4	{本地视频,自动导入,演示}	/demo-covers/4K-Abstract-Sci-Fi-Tunnel-VJ-Motion-Back-46c97941.jpg?v=1779535757	/demo-videos/4K Abstract Sci-Fi Tunnel VJ Motion Background __ Neon Light Tunnel Free VJ Loops __ 4K VJ Loops.mp4	596	9	27725	2747	9	709	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	0	2026-05-23 11:29:16.268248+00	2026-05-23 11:29:16.268248+00
854f52a4-a565-4a99-a1af-1cd3c4358edc	After Effects   Trapcode Particular Bounce (1080P)	这是系统自动从 public/demo-videos 目录读取的视频文件：After Effects - Trapcode Particular bounce-(1080p).mp4	{本地视频,自动导入,演示}	/demo-covers/After-Effects---Trapcode-Particular-boun-8adeef48.jpg?v=1779535757	/demo-videos/After Effects - Trapcode Particular bounce-(1080p).mp4	60	8	47130	653	17	288	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	0	2026-05-23 11:29:16.268248+00	2026-05-23 11:29:16.268248+00
9f4e79d8-bfef-4212-b981-a8b6efa96049	Background, Green Screen, Motion Graphics, Animated Background, Copyright Free (1080P)	这是系统自动从 public/demo-videos 目录读取的视频文件：Background, Green Screen, Motion Graphics, Animated Background, Copyright Free-(1080p).mp4	{本地视频,自动导入,演示}	/demo-covers/Background-Green-Screen-Motion-Graphics--ea959c3e.jpg?v=1779535758	/demo-videos/Background, Green Screen, Motion Graphics, Animated Background, Copyright Free-(1080p).mp4	60	5	39217	2448	21	483	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	0	2026-05-23 11:29:16.268248+00	2026-05-23 11:29:16.268248+00
1ff9a689-7bb3-48c6-be73-bee778308624	Beihang2025	这是系统自动从 public/demo-videos 目录读取的视频文件：beihang2025.mp4	{本地视频,自动导入,演示}	/demo-covers/beihang2025-20388e70.jpg?v=1779535758	/demo-videos/beihang2025.mp4	240	7	5546	1610	12	55	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	0	2026-05-23 11:29:16.268248+00	2026-05-23 11:29:16.268248+00
08c54878-6298-4d87-8a52-fe55282328e6	Goldendust   Free Video Background Loop Hd 1080P (1080P)	这是系统自动从 public/demo-videos 目录读取的视频文件：GoldenDust - FREE Video Background Loop HD 1080p-(1080p).mp4	{本地视频,自动导入,演示}	/demo-covers/GoldenDust---FREE-Video-Background-Loop--00d5ae29.jpg?v=1779535759	/demo-videos/GoldenDust - FREE Video Background Loop HD 1080p-(1080p).mp4	596	7	45842	1755	22	481	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	0	2026-05-23 11:29:16.268248+00	2026-05-23 11:29:16.268248+00
6c446ba8-4b54-401f-886b-37423aeeb6ea	This Is Beihang	这是系统自动从 public/demo-videos 目录读取的视频文件：This-is-beihang.mp4	{本地视频,自动导入,演示}	/demo-covers/This-is-beihang-b72d1e76.jpg?v=1779535759	/demo-videos/This-is-beihang.mp4	596	6	5382	1392	11	121	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	0	2026-05-23 11:29:16.268248+00	2026-05-23 11:29:16.268248+00
dfe163e6-d267-4da2-a18d-f16bd03ccb5f	Video1	这是系统自动从 public/demo-videos 目录读取的视频文件：video1.mp4	{本地视频,自动导入,演示}	/demo-covers/video1-ef4ac246.jpg?v=1779535761	/demo-videos/video1.mp4	596	2	28619	659	2	119	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	0	2026-05-23 11:29:16.268248+00	2026-05-23 11:29:16.268248+00
d511a70a-8e3f-40bf-b237-57465e7758d9	Video2	这是系统自动从 public/demo-videos 目录读取的视频文件：video2.mp4	{本地视频,自动导入,演示}	/demo-covers/video2-4d0cd2c1.jpg?v=1779535763	/demo-videos/video2.mp4	300	8	31205	2817	20	663	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	0	2026-05-23 11:29:16.268248+00	2026-05-23 11:29:16.268248+00
76ad3f2b-1cdb-4893-9f1f-6df151dc5dd8	中国风元素晚会演绎Led背景视频 (1080P)	这是系统自动从 public/demo-videos 目录读取的视频文件：中国风元素晚会演绎LED背景视频-(1080p).mp4	{本地视频,自动导入,演示}	/demo-covers/LED---1080p-9dd32a7e.jpg?v=1779535763	/demo-videos/中国风元素晚会演绎LED背景视频-(1080p).mp4	596	2	34559	2239	5	41	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	0	2026-05-23 11:29:16.268248+00	2026-05-23 11:29:16.268248+00
e9fe0cce-4b4f-4b17-965f-e3a720ba0c05	中国风大气Led大屏幕特效画面 (1080P)	这是系统自动从 public/demo-videos 目录读取的视频文件：中国风大气LED大屏幕特效画面-(1080p).mp4	{本地视频,自动导入,演示}	/demo-covers/LED---1080p-195a7fb8.jpg?v=1779535764	/demo-videos/中国风大气LED大屏幕特效画面-(1080p).mp4	60	3	33982	1321	28	731	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	0	2026-05-23 11:29:16.268248+00	2026-05-23 11:29:16.268248+00
1604e2d2-0227-4d60-b978-a4b190bd0cd0	致敬Beyond經典之《海闊天空》	这是系统自动从 public/demo-videos 目录读取的视频文件：致敬beyond經典之《海闊天空》.mp4	{本地视频,自动导入,演示}	/demo-covers/beyond-dbe4073c.jpg?v=1779535764	/demo-videos/致敬beyond經典之《海闊天空》.mp4	300	7	35460	396	22	350	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	0	2026-05-23 11:29:16.268248+00	2026-05-23 11:29:16.268248+00
1f1afb7c-fe2e-44b6-a877-1273bbf04ea0	花瓣飘落唯美背景素材 (720P)	这是系统自动从 public/demo-videos 目录读取的视频文件：花瓣飘落唯美背景素材-(720p).mp4	{本地视频,自动导入,演示}	/demo-covers/720p-6796bea3.jpg?v=1779535764	/demo-videos/花瓣飘落唯美背景素材-(720p).mp4	60	6	46094	2725	14	943	3931ea83-5e99-47d3-a38b-ba96e9ed59e2	1	0	2026-05-23 11:29:16.268248+00	2026-05-23 11:29:16.268248+00
\.


--
-- Name: categories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.categories_id_seq', 1, false);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: comments comments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_pkey PRIMARY KEY (id);


--
-- Name: danmaku danmaku_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.danmaku
    ADD CONSTRAINT danmaku_pkey PRIMARY KEY (id);


--
-- Name: live_rooms live_rooms_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_rooms
    ADD CONSTRAINT live_rooms_pkey PRIMARY KEY (id);


--
-- Name: live_rooms live_rooms_stream_key_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_rooms
    ADD CONSTRAINT live_rooms_stream_key_key UNIQUE (stream_key);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: videos videos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_pkey PRIMARY KEY (id);


--
-- Name: ix_users_account; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_users_account ON public.users USING btree (account);


--
-- Name: comments comments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: comments comments_video_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_video_id_fkey FOREIGN KEY (video_id) REFERENCES public.videos(id);


--
-- Name: danmaku danmaku_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.danmaku
    ADD CONSTRAINT danmaku_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: live_rooms live_rooms_anchor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_rooms
    ADD CONSTRAINT live_rooms_anchor_id_fkey FOREIGN KEY (anchor_id) REFERENCES public.users(id);


--
-- Name: live_rooms live_rooms_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_rooms
    ADD CONSTRAINT live_rooms_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: videos videos_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: videos videos_uploader_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_uploader_id_fkey FOREIGN KEY (uploader_id) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--


