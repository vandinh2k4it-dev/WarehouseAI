--
-- PostgreSQL database dump
--

\restrict RJVxGeeqcrPSGa9p5dYZ2a98lux2p5n5F0b2PCjaGKMrLDNlfnxrALckGm8XNK3

-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
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
-- Name: alerts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alerts (
    id integer NOT NULL,
    alert_type character varying(30) NOT NULL,
    severity character varying(10) DEFAULT 'medium'::character varying NOT NULL,
    inventory_id integer,
    reconciliation_id integer,
    message text NOT NULL,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    CONSTRAINT alerts_alert_type_check CHECK (((alert_type)::text = ANY ((ARRAY['low_stock'::character varying, 'expiring_soon'::character varying, 'discrepancy'::character varying])::text[]))),
    CONSTRAINT alerts_severity_check CHECK (((severity)::text = ANY ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying])::text[]))),
    CONSTRAINT alerts_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'acknowledged'::character varying, 'resolved'::character varying])::text[])))
);


ALTER TABLE public.alerts OWNER TO postgres;

--
-- Name: alerts_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.alerts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.alerts_id_seq OWNER TO postgres;

--
-- Name: alerts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.alerts_id_seq OWNED BY public.alerts.id;


--
-- Name: camera_count_sessions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.camera_count_sessions (
    id integer NOT NULL,
    session_code character varying(64),
    camera_id character varying(64),
    linked_receipt_id integer,
    video_path character varying(512),
    counted_quantity integer,
    avg_detection_confidence numeric(5,4),
    model_version character varying(64),
    started_at timestamp with time zone,
    ended_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    direction character varying(10) DEFAULT 'import'::character varying NOT NULL,
    receipt_line_item_id integer,
    product_id integer,
    expected_quantity numeric(12,2),
    status character varying(20) DEFAULT 'counting'::character varying NOT NULL,
    CONSTRAINT camera_count_sessions_direction_check CHECK (((direction)::text = ANY ((ARRAY['import'::character varying, 'export'::character varying])::text[]))),
    CONSTRAINT camera_count_sessions_status_check CHECK (((status)::text = ANY ((ARRAY['counting'::character varying, 'completed'::character varying, 'needs_review'::character varying, 'resolved_override'::character varying, 'superseded'::character varying])::text[])))
);


ALTER TABLE public.camera_count_sessions OWNER TO postgres;

--
-- Name: camera_count_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.camera_count_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.camera_count_sessions_id_seq OWNER TO postgres;

--
-- Name: camera_count_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.camera_count_sessions_id_seq OWNED BY public.camera_count_sessions.id;


--
-- Name: import_receipts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.import_receipts (
    id integer NOT NULL,
    receipt_code character varying(64),
    store_location character varying(255),
    image_path character varying(512),
    ocr_raw_text text,
    ocr_confidence numeric(5,4),
    status character varying(20) DEFAULT 'pending_ocr'::character varying NOT NULL,
    received_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    source_type character varying(20) DEFAULT 'ocr'::character varying NOT NULL,
    CONSTRAINT import_receipts_source_type_check CHECK (((source_type)::text = ANY ((ARRAY['ocr'::character varying, 'manual'::character varying])::text[]))),
    CONSTRAINT import_receipts_status_check CHECK (((status)::text = ANY ((ARRAY['pending_ocr'::character varying, 'ocr_done'::character varying, 'reconciled'::character varying, 'flagged'::character varying])::text[])))
);


ALTER TABLE public.import_receipts OWNER TO postgres;

--
-- Name: import_receipts_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.import_receipts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.import_receipts_id_seq OWNER TO postgres;

--
-- Name: import_receipts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.import_receipts_id_seq OWNED BY public.import_receipts.id;


--
-- Name: inventory; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.inventory (
    id integer NOT NULL,
    product_id integer NOT NULL,
    batch_code character varying(64) NOT NULL,
    quantity numeric(12,2) DEFAULT 0 NOT NULL,
    expiry_date date,
    last_updated timestamp with time zone DEFAULT now() NOT NULL,
    location character varying(50)
);


ALTER TABLE public.inventory OWNER TO postgres;

--
-- Name: inventory_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.inventory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.inventory_id_seq OWNER TO postgres;

--
-- Name: inventory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.inventory_id_seq OWNED BY public.inventory.id;


--
-- Name: inventory_transactions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.inventory_transactions (
    id integer NOT NULL,
    inventory_id integer NOT NULL,
    change_qty numeric(12,2) NOT NULL,
    transaction_type character varying(20) NOT NULL,
    reference_type character varying(20),
    reference_id integer,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT inventory_transactions_transaction_type_check CHECK (((transaction_type)::text = ANY ((ARRAY['import'::character varying, 'export'::character varying, 'adjustment'::character varying])::text[])))
);


ALTER TABLE public.inventory_transactions OWNER TO postgres;

--
-- Name: inventory_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.inventory_transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.inventory_transactions_id_seq OWNER TO postgres;

--
-- Name: inventory_transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.inventory_transactions_id_seq OWNED BY public.inventory_transactions.id;


--
-- Name: products; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.products (
    id integer NOT NULL,
    sku character varying(64),
    name character varying(255) NOT NULL,
    category character varying(100),
    unit character varying(32) DEFAULT 'thùng'::character varying NOT NULL,
    low_stock_threshold numeric(12,2) DEFAULT 10,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.products OWNER TO postgres;

--
-- Name: products_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.products_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.products_id_seq OWNER TO postgres;

--
-- Name: products_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.products_id_seq OWNED BY public.products.id;


--
-- Name: push_subscriptions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.push_subscriptions (
    id integer NOT NULL,
    endpoint text NOT NULL,
    p256dh text NOT NULL,
    auth text NOT NULL,
    label character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.push_subscriptions OWNER TO postgres;

--
-- Name: push_subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.push_subscriptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.push_subscriptions_id_seq OWNER TO postgres;

--
-- Name: push_subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.push_subscriptions_id_seq OWNED BY public.push_subscriptions.id;


--
-- Name: receipt_line_items; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.receipt_line_items (
    id integer NOT NULL,
    receipt_id integer NOT NULL,
    line_no integer NOT NULL,
    product_name_raw character varying(255) NOT NULL,
    product_id integer,
    quantity numeric(12,2) NOT NULL,
    batch_code character varying(64),
    expiry_date date,
    match_score numeric(5,4),
    field_confidence jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.receipt_line_items OWNER TO postgres;

--
-- Name: receipt_line_items_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.receipt_line_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.receipt_line_items_id_seq OWNER TO postgres;

--
-- Name: receipt_line_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.receipt_line_items_id_seq OWNED BY public.receipt_line_items.id;


--
-- Name: reconciliations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reconciliations (
    id integer NOT NULL,
    receipt_id integer,
    receipt_line_item_id integer,
    product_id integer,
    session_id integer NOT NULL,
    receipt_total numeric(12,2) NOT NULL,
    camera_total integer NOT NULL,
    difference numeric(12,2) NOT NULL,
    threshold_used numeric(5,4) NOT NULL,
    status character varying(20) DEFAULT 'matched'::character varying NOT NULL,
    resolved_by character varying(100),
    resolved_note text,
    resolved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT reconciliations_status_check CHECK (((status)::text = ANY ((ARRAY['matched'::character varying, 'flagged'::character varying, 'resolved_manual'::character varying, 'resolved_override'::character varying])::text[])))
);


ALTER TABLE public.reconciliations OWNER TO postgres;

--
-- Name: reconciliations_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.reconciliations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reconciliations_id_seq OWNER TO postgres;

--
-- Name: reconciliations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.reconciliations_id_seq OWNED BY public.reconciliations.id;


--
-- Name: alerts id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts ALTER COLUMN id SET DEFAULT nextval('public.alerts_id_seq'::regclass);


--
-- Name: camera_count_sessions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.camera_count_sessions ALTER COLUMN id SET DEFAULT nextval('public.camera_count_sessions_id_seq'::regclass);


--
-- Name: import_receipts id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.import_receipts ALTER COLUMN id SET DEFAULT nextval('public.import_receipts_id_seq'::regclass);


--
-- Name: inventory id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory ALTER COLUMN id SET DEFAULT nextval('public.inventory_id_seq'::regclass);


--
-- Name: inventory_transactions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_transactions ALTER COLUMN id SET DEFAULT nextval('public.inventory_transactions_id_seq'::regclass);


--
-- Name: products id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products ALTER COLUMN id SET DEFAULT nextval('public.products_id_seq'::regclass);


--
-- Name: push_subscriptions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.push_subscriptions ALTER COLUMN id SET DEFAULT nextval('public.push_subscriptions_id_seq'::regclass);


--
-- Name: receipt_line_items id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.receipt_line_items ALTER COLUMN id SET DEFAULT nextval('public.receipt_line_items_id_seq'::regclass);


--
-- Name: reconciliations id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reconciliations ALTER COLUMN id SET DEFAULT nextval('public.reconciliations_id_seq'::regclass);


--
-- Data for Name: alerts; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.alerts (id, alert_type, severity, inventory_id, reconciliation_id, message, status, created_at, resolved_at) FROM stdin;
20	discrepancy	high	\N	25	[IMPORT] Lệch +11 khi đếm 'Mì Kokomi' — camera đếm 35, cần 24 (vượt ngưỡng 0.0%). Chưa cập nhật tồn kho cho loại này — cần kiểm tra lại (phiên #30).	acknowledged	2026-09-15 15:36:32.923069+07	\N
18	discrepancy	high	\N	22	[IMPORT] Lệch -10 khi đếm 'Mỳ Hảo Hảo' — camera đếm 90, cần 100 (vượt ngưỡng 2.0%). Chưa cập nhật tồn kho cho loại này — cần kiểm tra lại (phiên #26).	acknowledged	2026-09-15 14:52:07.314188+07	\N
19	discrepancy	high	\N	24	[IMPORT] Lệch +11 khi đếm 'Mì Kokomi' — camera đếm 35, cần 24 (vượt ngưỡng 0.0%). Chưa cập nhật tồn kho cho loại này — cần kiểm tra lại (phiên #28).	acknowledged	2026-09-15 15:17:43.449529+07	\N
4	expiring_soon	medium	8	\N	Lô 'L881M' của 'Coca-Cola lon 330ml' sắp hết hạn trong 17 ngày (HSD 2026-10-02).	acknowledged	2026-09-15 14:16:03.44597+07	\N
5	low_stock	medium	10	\N	Sản phẩm 'Nước tăng lực Sting dâu 330ml' (lô L649D) chỉ còn 11.00 thùng — dưới ngưỡng 15.00.	acknowledged	2026-09-15 14:16:03.44597+07	\N
6	low_stock	medium	14	\N	Sản phẩm 'Bánh Oreo hộp 133g' (lô L987D) chỉ còn 2.00 thùng — dưới ngưỡng 10.00.	acknowledged	2026-09-15 14:16:03.44597+07	\N
7	expiring_soon	medium	14	\N	Lô 'L987D' của 'Bánh Oreo hộp 133g' sắp hết hạn trong 19 ngày (HSD 2026-10-04).	acknowledged	2026-09-15 14:16:03.44597+07	\N
8	low_stock	medium	19	\N	Sản phẩm 'Kẹo Alpenliebe' (lô L324Z) chỉ còn 4.00 thùng — dưới ngưỡng 12.00.	acknowledged	2026-09-15 14:16:03.44597+07	\N
9	expiring_soon	medium	20	\N	Lô 'L941B' của 'Snack Oishi khoai tây' sắp hết hạn trong 17 ngày (HSD 2026-10-02).	acknowledged	2026-09-15 14:16:03.44597+07	\N
10	low_stock	medium	24	\N	Sản phẩm 'Cháo gói Kinh Đô' (lô L369V) chỉ còn 10.00 thùng — dưới ngưỡng 15.00.	acknowledged	2026-09-15 14:16:03.44597+07	\N
12	expiring_soon	medium	27	\N	Lô 'L742F' của 'Dầu ăn Simply 1L' sắp hết hạn trong 18 ngày (HSD 2026-10-03).	acknowledged	2026-09-15 14:16:03.44597+07	\N
13	low_stock	medium	28	\N	Sản phẩm 'Dầu ăn Neptune 1L' (lô L165P) chỉ còn 3.00 thùng — dưới ngưỡng 8.00.	acknowledged	2026-09-15 14:16:03.44597+07	\N
32	low_stock	medium	15	\N	Sản phẩm 'Bánh Cosy quy bơ' (lô L954N) chỉ còn 8.0 thùng — dưới ngưỡng 10.00.	acknowledged	2026-10-04 14:26:28.99782+07	\N
31	low_stock	high	57	\N	Sản phẩm 'Bánh AFC' (lô L441Z) chỉ còn 0.0 thùng — dưới ngưỡng 10.00.	acknowledged	2026-10-04 14:26:06.24375+07	\N
30	low_stock	high	44	\N	Sản phẩm 'Bánh Solite hộp' (lô L165M) chỉ còn 0.0 thùng — dưới ngưỡng 10.00.	acknowledged	2026-10-04 13:40:38.686719+07	\N
29	low_stock	high	13	\N	Sản phẩm 'Cà phê hòa tan G7 3in1' (lô L333L) chỉ còn 0.0 thùng — dưới ngưỡng 10.00.	acknowledged	2026-10-04 13:05:49.212544+07	\N
28	low_stock	high	14	\N	Sản phẩm 'Bánh Oreo hộp 133g' (lô L987D) chỉ còn 0.0 thùng — dưới ngưỡng 10.00.	acknowledged	2026-10-04 13:01:23.914355+07	\N
27	low_stock	high	33	\N	Sản phẩm 'Bột giặt Omo 3kg' (lô L880F) chỉ còn 0.0 thùng — dưới ngưỡng 6.00.	acknowledged	2026-10-04 12:59:51.736227+07	\N
26	discrepancy	high	\N	35	[IMPORT] Lệch -382 khi đếm 'Dầu gội Sunsilk' — camera đếm 17, cần 399 (vượt ngưỡng 0.0%). Chưa cập nhật tồn kho cho loại này — cần kiểm tra lại (phiên #42).	acknowledged	2026-10-04 12:50:26.876461+07	\N
25	discrepancy	high	\N	34	[IMPORT] Lệch -270 khi đếm 'Coca Cola 390ml' — camera đếm 35, cần 305 (vượt ngưỡng 0.0%). Chưa cập nhật tồn kho cho loại này — cần kiểm tra lại (phiên #41).	acknowledged	2026-10-04 12:48:43.407656+07	\N
24	discrepancy	high	\N	32	[IMPORT] Lệch -2 khi đếm 'Mì Omachi' — camera đếm 5, cần 7 (vượt ngưỡng 0.0%). Chưa cập nhật tồn kho cho loại này — cần kiểm tra lại (phiên #39).	acknowledged	2026-10-04 12:46:52.562462+07	\N
23	discrepancy	high	\N	30	[IMPORT] Lệch -13 khi đếm 'Nước Aquafina' — camera đếm 25, cần 38 (vượt ngưỡng 0.0%). Chưa cập nhật tồn kho cho loại này — cần kiểm tra lại (phiên #37).	acknowledged	2026-09-22 18:21:20.970113+07	\N
22	discrepancy	high	\N	28	[IMPORT] Lệch -113 khi đếm 'Bánh Oreo' — camera đếm 21, cần 134 (vượt ngưỡng 0.0%). Chưa cập nhật tồn kho cho loại này — cần kiểm tra lại (phiên #34).	acknowledged	2026-09-19 15:08:36.540175+07	\N
21	discrepancy	high	\N	27	[IMPORT] Lệch -99 khi đếm 'Bánh Oreo' — camera đếm 35, cần 134 (vượt ngưỡng 0.0%). Chưa cập nhật tồn kho cho loại này — cần kiểm tra lại (phiên #33).	acknowledged	2026-09-19 15:06:57.678293+07	\N
16	low_stock	medium	36	\N	Sản phẩm 'Nước rửa chén Sunlight' (lô L100X) chỉ còn 3.00 thùng — dưới ngưỡng 8.00.	acknowledged	2026-09-15 14:16:03.44597+07	\N
15	low_stock	medium	35	\N	Sản phẩm 'Nước xả Comfort 1.5L' (lô L482F) chỉ còn 6.00 thùng — dưới ngưỡng 8.00.	acknowledged	2026-09-15 14:16:03.44597+07	\N
14	expiring_soon	high	33	\N	Lô 'L880F' của 'Bột giặt Omo 3kg' sắp hết hạn trong 8 ngày (HSD 2026-09-23).	acknowledged	2026-09-15 14:16:03.44597+07	\N
11	expiring_soon	high	26	\N	Lô 'L605C' của 'Dầu ăn Simply 1L' sắp hết hạn trong 8 ngày (HSD 2026-09-23).	acknowledged	2026-09-15 14:16:03.44597+07	\N
3	low_stock	medium	2	\N	Sản phẩm 'Sữa tươi Vinamilk 1L' (lô L328E) chỉ còn 14.00 thùng — dưới ngưỡng 15.00.	acknowledged	2026-09-15 14:16:03.44597+07	\N
2	low_stock	medium	1	\N	Sản phẩm 'Sữa tươi Vinamilk 1L' (lô L754D) chỉ còn 4.00 thùng — dưới ngưỡng 15.00.	acknowledged	2026-09-15 14:16:03.44597+07	\N
17	low_stock	medium	37	\N	Sản phẩm 'Nước rửa chén Sunlight' (lô L471L) chỉ còn 2.00 thùng — dưới ngưỡng 8.00.	acknowledged	2026-09-15 14:16:03.44597+07	\N
1	discrepancy	high	\N	11	[NHẬP] Lệch -30 khi đếm 'Hạt nêm Knorr' — camera đếm 53, cần 83 (vượt ngưỡng 2.0%). Chưa cập nhật tồn kho cho dòng này — cần kiểm tra lại (phiên #11).	acknowledged	2026-09-15 14:16:03.3981+07	\N
\.


--
-- Data for Name: camera_count_sessions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.camera_count_sessions (id, session_code, camera_id, linked_receipt_id, video_path, counted_quantity, avg_detection_confidence, model_version, started_at, ended_at, created_at, direction, receipt_line_item_id, product_id, expected_quantity, status) FROM stdin;
1	DEM0001	cam-01	1	\N	82	0.9600	seed-manual	2026-08-21 14:16:03.350278+07	2026-08-21 14:19:03.350278+07	2026-09-15 14:16:03.329476+07	import	1	1	82.00	completed
2	DEM0002	cam-01	1	\N	92	0.9200	seed-manual	2026-08-21 14:16:03.350278+07	2026-08-21 14:20:03.350278+07	2026-09-15 14:16:03.329476+07	import	2	4	92.00	completed
3	DEM0003	cam-01	1	\N	296	0.9400	seed-manual	2026-08-21 14:16:03.350278+07	2026-08-21 14:21:03.350278+07	2026-09-15 14:16:03.329476+07	import	3	17	296.00	completed
4	DEM0004	cam-01	1	\N	101	0.9700	seed-manual	2026-08-21 14:16:03.350278+07	2026-08-21 14:22:03.350278+07	2026-09-15 14:16:03.329476+07	import	4	26	101.00	completed
5	DEM0005	cam-01	2	\N	145	0.8600	seed-manual	2026-08-25 14:16:03.382749+07	2026-08-25 14:19:03.382749+07	2026-09-15 14:16:03.38355+07	import	5	11	145.00	completed
6	DEM0006	cam-01	2	\N	107	0.9200	seed-manual	2026-08-25 14:16:03.382749+07	2026-08-25 14:20:03.382749+07	2026-09-15 14:16:03.38355+07	import	6	13	107.00	completed
7	DEM0007	cam-01	2	\N	108	0.8600	seed-manual	2026-08-25 14:16:03.382749+07	2026-08-25 14:21:03.382749+07	2026-09-15 14:16:03.38355+07	import	7	14	108.00	completed
8	DEM0008	cam-01	2	\N	211	0.9600	seed-manual	2026-08-25 14:16:03.382749+07	2026-08-25 14:22:03.382749+07	2026-09-15 14:16:03.38355+07	import	8	16	211.00	completed
9	DEM0009	cam-01	3	\N	68	0.9000	seed-manual	2026-09-09 14:16:03.395702+07	2026-09-09 14:18:03.395702+07	2026-09-15 14:16:03.3981+07	import	9	21	68.00	completed
10	DEM0010	cam-01	3	\N	221	0.9000	seed-manual	2026-09-09 14:16:03.395702+07	2026-09-09 14:19:03.395702+07	2026-09-15 14:16:03.3981+07	import	10	23	221.00	completed
11	DEM0011	cam-01	3	\N	53	0.9000	seed-manual	2026-09-09 14:16:03.395702+07	2026-09-09 14:20:03.395702+07	2026-09-15 14:16:03.3981+07	import	11	25	83.00	needs_review
12	DEM0012	cam-01	4	\N	250	0.8600	seed-manual	2026-09-07 14:16:03.406997+07	2026-09-07 14:19:03.406997+07	2026-09-15 14:16:03.407698+07	import	12	2	250.00	completed
13	DEM0013	cam-01	4	\N	218	0.9000	seed-manual	2026-09-07 14:16:03.406997+07	2026-09-07 14:20:03.406997+07	2026-09-15 14:16:03.407698+07	import	13	6	218.00	completed
14	DEM0014	cam-01	4	\N	271	0.9300	seed-manual	2026-09-07 14:16:03.406997+07	2026-09-07 14:21:03.406997+07	2026-09-15 14:16:03.407698+07	import	14	9	271.00	completed
15	DEM0015	cam-01	6	\N	158	0.8800	seed-manual	2026-09-10 14:16:03.41813+07	2026-09-10 14:19:03.41813+07	2026-09-15 14:16:03.418846+07	import	18	3	158.00	completed
16	DEM0016	cam-01	6	\N	286	0.9500	seed-manual	2026-09-10 14:16:03.41813+07	2026-09-10 14:20:03.41813+07	2026-09-15 14:16:03.418846+07	import	19	10	286.00	completed
17	DEM0017	cam-01	6	\N	190	0.9700	seed-manual	2026-09-10 14:16:03.41813+07	2026-09-10 14:21:03.41813+07	2026-09-15 14:16:03.418846+07	import	20	30	190.00	completed
18	PX0001	\N	\N	\N	15	\N	\N	2026-09-15 14:16:03.430381+07	2026-09-15 14:16:03.430381+07	2026-09-15 14:16:03.42905+07	export	\N	4	15.00	completed
19	PX0002	\N	\N	\N	40	\N	\N	2026-09-15 14:16:03.430381+07	2026-09-15 14:16:03.430381+07	2026-09-15 14:16:03.42905+07	export	\N	17	40.00	completed
20	PX0003	\N	\N	\N	20	\N	\N	2026-09-14 14:16:03.436454+07	2026-09-14 14:16:03.436454+07	2026-09-15 14:16:03.42905+07	export	\N	11	20.00	completed
33	DEM0030	\N	12	uploads\\camera_videos\\session_33_1789805218_video_thu.mp4	35	0.8131	models/carton_counter_best.pt	2026-09-19 15:06:51.399551+07	2026-09-19 15:08:03.414371+07	2026-09-19 15:06:51.387986+07	import	35	36	134.00	superseded
21	DEM0018	\N	8	\N	273	\N	\N	2026-09-15 14:36:39.366075+07	2026-09-15 14:36:54.898622+07	2026-09-15 14:36:39.357799+07	import	21	31	273.00	completed
22	DEM0019	\N	8	\N	400	\N	\N	2026-09-15 14:37:07.904754+07	2026-09-15 14:37:11.895755+07	2026-09-15 14:37:07.902142+07	import	22	33	400.00	completed
23	DEM0020	\N	8	\N	204	\N	\N	2026-09-15 14:37:14.73051+07	2026-09-15 14:37:17.946433+07	2026-09-15 14:37:14.728503+07	import	23	32	204.00	completed
40	DEM0036	\N	14	\N	7	\N	\N	2026-10-04 12:46:57.172608+07	2026-10-04 12:47:04.741562+07	2026-10-04 12:46:57.168665+07	import	43	40	7.00	completed
24	DEM0021	\N	8	\N	320	\N	\N	2026-09-15 14:37:21.603624+07	2026-09-15 14:37:24.805319+07	2026-09-15 14:37:21.601269+07	import	24	23	320.00	completed
25	DEM0022	\N	5	\N	\N	\N	\N	2026-09-15 14:44:10.666567+07	\N	2026-09-15 14:44:10.66476+07	import	15	18	42.00	counting
34	DEM0031	\N	12	uploads\\camera_videos\\session_34_1789805317_video_thu.mp4	21	0.8639	models/carton_counter_best.pt	2026-09-19 15:08:29.43041+07	2026-09-19 15:09:34.116685+07	2026-09-19 15:08:29.422848+07	import	35	36	134.00	superseded
35	DEM0032	\N	12	\N	\N	\N	\N	2026-09-19 15:11:50.666474+07	\N	2026-09-19 15:11:50.660794+07	import	35	36	134.00	superseded
27	DEM0024	\N	9	\N	119	\N	\N	2026-09-15 14:52:15.889853+07	2026-09-15 14:52:20.748861+07	2026-09-15 14:52:15.892365+07	import	26	35	120.00	completed
26	DEM0023	\N	9	\N	90	\N	\N	2026-09-15 14:52:00.815691+07	2026-09-15 14:52:07.313069+07	2026-09-15 14:52:00.813886+07	import	25	34	100.00	resolved_override
28	DEM0025	\N	10	uploads\\camera_videos\\session_28_1789460263_video_thu.mp4	35	0.8131	models/carton_counter_best.pt	2026-09-15 15:17:38.427238+07	2026-09-15 15:18:46.553993+07	2026-09-15 15:17:38.422889+07	import	29	37	24.00	superseded
29	DEM0026	\N	10	\N	\N	\N	\N	2026-09-15 15:36:16.855658+07	\N	2026-09-15 15:36:16.843416+07	import	29	37	24.00	superseded
36	DEM0033	\N	12	\N	134	\N	\N	2026-09-19 15:12:00.166687+07	2026-09-19 15:12:05.105965+07	2026-09-19 15:12:00.162558+07	import	35	36	134.00	completed
30	DEM0027	\N	10	uploads\\camera_videos\\session_30_1789461393_video_thu.mp4	35	0.8131	models/carton_counter_best.pt	2026-09-15 15:36:21.849292+07	2026-09-15 15:37:41.732876+07	2026-09-15 15:36:21.846387+07	import	29	37	24.00	needs_review
31	DEM0028	\N	12	\N	\N	\N	\N	2026-09-19 14:00:36.055404+07	\N	2026-09-19 14:00:36.04478+07	import	37	37	93.00	superseded
32	DEM0029	\N	12	\N	93	\N	\N	2026-09-19 14:00:44.345296+07	2026-09-19 14:00:50.192116+07	2026-09-19 14:00:44.338315+07	import	37	37	93.00	completed
48	PX0010	\N	\N	\N	204	\N	\N	2026-10-04 14:25:58.260388+07	2026-10-04 14:26:06.247346+07	2026-10-04 14:25:58.250908+07	export	\N	32	204.00	completed
41	DEM0037	\N	14	uploads\\camera_videos\\session_41_1791092924_video_thu.mp4	35	0.8131	models/carton_counter_best.pt	2026-10-04 12:48:38.581381+07	2026-10-04 12:49:52.010423+07	2026-10-04 12:48:38.577401+07	import	45	6	305.00	needs_review
37	DEM0034	\N	13	uploads\\camera_videos\\session_37_1790076081_video_thu.mp4	25	0.8534	models/carton_counter_best.pt	2026-09-22 18:21:08.209098+07	2026-09-22 18:22:22.073267+07	2026-09-22 18:21:08.198021+07	import	39	39	38.00	needs_review
38	PX0004	\N	\N	\N	20	\N	\N	2026-09-30 13:56:10.574223+07	2026-09-30 13:56:14.397498+07	2026-09-30 13:56:10.551876+07	export	\N	13	20.00	completed
45	PX0007	\N	\N	\N	12	\N	\N	2026-10-04 13:05:46.51417+07	2026-10-04 13:05:49.212748+07	2026-10-04 13:05:46.513053+07	export	\N	10	12.00	completed
42	DEM0038	\N	14	uploads\\camera_videos\\session_42_1791093027_video_thu.mp4	17	0.8733	models/carton_counter_best.pt	2026-10-04 12:50:13.253166+07	2026-10-04 12:51:32.476712+07	2026-10-04 12:50:13.249385+07	import	47	33	399.00	needs_review
39	DEM0035	\N	14	\N	5	\N	\N	2026-10-04 12:46:38.674589+07	2026-10-04 12:46:52.565512+07	2026-10-04 12:46:38.664725+07	import	43	40	7.00	superseded
43	PX0005	\N	\N	\N	9	\N	\N	2026-10-04 12:59:48.204122+07	2026-10-04 12:59:51.736426+07	2026-10-04 12:59:48.202489+07	export	\N	26	9.00	completed
44	PX0006	\N	\N	\N	2	\N	\N	2026-10-04 13:01:21.046643+07	2026-10-04 13:01:23.915088+07	2026-10-04 13:01:21.045242+07	export	\N	11	2.00	completed
46	PX0008	\N	\N	\N	12	\N	\N	2026-10-04 13:06:25.97839+07	2026-10-04 13:06:31.304896+07	2026-10-04 13:06:25.977218+07	export	\N	10	12.00	completed
47	PX0009	\N	\N	\N	88	\N	\N	2026-10-04 13:40:35.349303+07	2026-10-04 13:40:38.688373+07	2026-10-04 13:40:35.345624+07	export	\N	13	88.00	completed
49	PX0011	\N	\N	\N	10	\N	\N	2026-10-04 14:26:25.996176+07	2026-10-04 14:26:28.996766+07	2026-10-04 14:26:25.99416+07	export	\N	12	10.00	completed
\.


--
-- Data for Name: import_receipts; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.import_receipts (id, receipt_code, store_location, image_path, ocr_raw_text, ocr_confidence, status, received_at, created_at, source_type) FROM stdin;
1	PN0001	Công ty TNHH An Bình	./uploads/receipts/seed_PN0001.jpg	Phiếu nhập PN0001 — dữ liệu seed, không qua OCR thật.	0.9700	reconciled	2026-08-21 14:16:03.350278+07	2026-09-15 14:16:03.329476+07	ocr
2	PN0002	Đại lý Minh Phát	./uploads/receipts/seed_PN0002.jpg	Phiếu nhập PN0002 — dữ liệu seed, không qua OCR thật.	0.9700	reconciled	2026-08-25 14:16:03.382749+07	2026-09-15 14:16:03.38355+07	ocr
3	PN0003	Công ty CP Thương mại Hưng Thịnh	./uploads/receipts/seed_PN0003.jpg	Phiếu nhập PN0003 — dữ liệu seed, không qua OCR thật.	0.9400	ocr_done	2026-09-09 14:16:03.395702+07	2026-09-15 14:16:03.3981+07	ocr
4	PN0004	Nhà phân phối Sài Gòn Food	\N	\N	\N	reconciled	2026-09-07 14:16:03.406997+07	2026-09-15 14:16:03.407698+07	manual
5	PN0005	Chành xe Miền Tây (giao tận kho)	\N	\N	\N	ocr_done	2026-09-15 03:16:03.415123+07	2026-09-15 14:16:03.415711+07	manual
6	PN0007	Công ty TNHH An Bình	./uploads/receipts/seed_PN0007.jpg	Phiếu nhập PN0007 — dữ liệu seed, không qua OCR thật.	0.9700	reconciled	2026-09-10 14:16:03.41813+07	2026-09-15 14:16:03.418846+07	ocr
8	PN0008	\N	./uploads/receipts\\c56b9697eed442ca8c266b52b974a9fe.png	PHIẾU NHẬP HÀNG H2\nNgày nhập: 10/01/2026/2006\nĐại lý: Công ty TNHH Thương mại Minh Phát\nTên sản phẩm\nSố lượng\nMã Iô\nHSD\nKem đánh răng P/S\n273\nL115T\n17/08/2028\nDầu gội Sunsilk\n400\nL100V\n03/10/2027\nBánh AFC\n204\nL441Z\n16/07/2026\nNước mắm Nam Ngư\n320\nLO68N\n28/03/2026\nNgười giao hàng:\nNgười nhận hàng:	1.0000	reconciled	2026-09-15 14:27:24.539282+07	2026-09-15 14:27:24.53738+07	ocr
9	PN0009	\N	\N	\N	\N	reconciled	2026-09-15 14:51:30.159613+07	2026-09-15 14:51:30.162394+07	manual
10	PN0010	\N	./uploads/receipts\\f40fd0dd4187416dadb322e87b30ef6f.png	PHIẾU NHẬP HÀNG H9\nNgày nhập: 12/02/2026/19\nĐại lý: Công ty TNHH Thương mại Minh Phát\nTên sản phẩm\nSố lượng\nMã Iô\nHSD\nBánh Oreo\n134\nL805D\n07/08/2028\nBánh Solite\n343\nL45OW\n31/03/2026\nMì Kokomi\n93\nLO16K\n19/08/2027\nDầu gội Sunsilk\n202\nLO15X\n05/07/2026\nNgười giao hàng:\nNgười nhận hàng:	1.0000	ocr_done	2026-09-15 15:12:10.896605+07	2026-09-15 15:12:10.896459+07	ocr
11	PN0011	\N	./uploads/receipts\\da4447e2be654c888803ffe95f9e37d7.png	PHIẾU NHẬP HÀNG H1\nNgày nhập: 15/10/2026/19\nĐại lý: công ty phân phối ABC\nTên sản phẩm\nSố lượng\nMã Iô\nHSD\nBột giặt Ariel\n271\nL1671\n13/10/2027\nTrà Ô Long Tea4\n212\nL222X\n15/10/2028\nSnack Oishi\n150\nL606Z\n26/12/2027\nBánh Solite\n208\nL157Z\n15/07/2028\nNgười giao hàng:\nNgười nhận hàng:	1.0000	ocr_done	2026-09-16 19:32:06.080012+07	2026-09-16 19:32:06.074059+07	ocr
12	PN0012	\N	./uploads/receipts\\2104f90ff18f48f48a527af93d9f831f.png	PHIẾU NHẬP HÀNG H9\nNgày nhập: 12/02/2026/19\nĐại lý: Công ty TNHH Thương mại Minh Phát\nTên sản phẩm\nSố lượng\nMã Iô\nHSD\nBánh Oreo\n134\nL805D\n07/08/2028\nBánh Solite\n343\nL45OW\n31/03/2026\nMì Kokomi\n93\nLO16K\n19/08/2027\nDầu gội Sunsilk\n202\nLO15X\n05/07/2026\nNgười giao hàng:\nNgười nhận hàng:	1.0000	ocr_done	2026-09-19 14:00:13.341746+07	2026-09-19 14:00:13.336521+07	ocr
13	PN0013	\N	./uploads/receipts\\2606c7bb6eb8436fb4300955658b1c9b.png	PHIẾU NHẬP HÀNG %3\nNgày nhập: 03/09/2026\nĐại lý: công ty phân phối CBC\nTên sản phẩm\nSố lượng\nMã Iô\nHSD\nNước Aquafina\n38\nL613P\n17/04/2027\nMì Omachi\n38\nL1371\n04/01/2027\nĐường Biên Hòa\n132\nL404Q\n03/08/2027\nNước mắm Nam Ngư\n138\nL769G\n16/09/2027\nNgười giao hàng:\nNgười nhận hàng:	1.0000	ocr_done	2026-09-22 18:20:31.95195+07	2026-09-22 18:20:31.947152+07	ocr
14	PN0014	\N	./uploads/receipts\\18790e5d863b418386cd0182faaf1d3d.png	PHIẾU NHẬP HÀNG H8\nNgày nhập: 22/07/2026\nĐại lý: Nhà phân phối Thành Đạt\nTên sản phẩm\nSố lượng\nMã Iô\nHSD\nMì Omachi\n7\nLOG6P\n09/10/2026\nCà phê G7\n260\nL288Y\n14/10/2028\nCoca Cola 390ml\n305\nL343Q\n29/04/2027\nSữa Vinamilk 180ml\n66\nLO7ER\n02/05/2026\nDầu gội Sunsilk\n399\nL662X\n15/05/2027\nNgười giao hàng:\nNgười nhận hàng:	1.0000	ocr_done	2026-10-04 12:46:05.645906+07	2026-10-04 12:46:05.64418+07	ocr
\.


--
-- Data for Name: inventory; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.inventory (id, product_id, batch_code, quantity, expiry_date, last_updated, location) FROM stdin;
1	1	L754D	4.00	2026-09-10	2026-09-12 14:16:03.3403+07	\N
2	1	L328E	14.00	2026-09-04	2026-09-07 14:16:03.340835+07	\N
3	2	L189V	35.00	2026-11-29	2026-09-14 14:16:03.340835+07	\N
4	3	L323H	25.00	2026-11-27	2026-09-07 14:16:03.340835+07	\N
6	5	L559V	41.00	2026-11-17	2026-09-13 14:16:03.340835+07	\N
7	5	L814Q	43.00	2027-02-01	2026-09-12 14:16:03.340835+07	\N
9	7	L467N	160.00	2026-12-06	2026-09-08 14:16:03.340835+07	\N
10	8	L649D	11.00	2027-05-26	2026-09-14 14:16:03.340835+07	\N
11	9	L665L	47.00	2027-09-26	2026-09-10 14:16:03.340835+07	\N
12	9	L691G	43.00	2026-12-07	2026-09-05 14:16:03.340835+07	\N
16	13	L786K	68.00	2027-10-11	2026-09-14 14:16:03.340835+07	\N
18	14	L573P	24.00	2027-10-07	2026-09-07 14:16:03.340835+07	\N
19	15	L324Z	4.00	2026-12-12	2026-09-12 14:16:03.340835+07	\N
20	16	L941B	46.00	2026-10-02	2026-09-11 14:16:03.341517+07	\N
21	17	L167G	99.00	2027-08-31	2026-09-10 14:16:03.341517+07	\N
22	17	L317Y	74.00	2027-10-09	2026-09-08 14:16:03.341517+07	\N
23	18	L246K	44.00	2027-08-28	2026-09-07 14:16:03.341517+07	\N
24	19	L369V	10.00	2026-09-05	2026-09-09 14:16:03.341517+07	\N
25	20	L470H	34.00	2027-01-23	2026-09-07 14:16:03.341517+07	\N
26	21	L605C	24.00	2026-09-23	2026-09-13 14:16:03.341517+07	\N
27	21	L742F	24.00	2026-10-03	2026-09-06 14:16:03.341517+07	\N
28	22	L165P	3.00	2027-07-11	2026-09-07 14:16:03.341517+07	\N
29	23	L357U	25.00	2026-11-19	2026-09-05 14:16:03.341517+07	\N
30	24	L838D	22.00	2027-08-15	2026-09-11 14:16:03.341517+07	\N
31	25	L887Y	53.00	2027-04-13	2026-09-09 14:16:03.341517+07	\N
32	25	L261R	40.00	2027-03-28	2026-09-07 14:16:03.341517+07	\N
34	27	L405Y	15.00	2027-02-23	2026-09-13 14:16:03.341517+07	\N
35	28	L482F	6.00	2026-09-02	2026-09-07 14:16:03.341517+07	\N
36	29	L100X	3.00	2026-11-23	2026-09-14 14:16:03.341517+07	\N
37	29	L471L	2.00	2027-03-17	2026-09-06 14:16:03.341517+07	\N
38	30	L180C	29.00	2026-12-19	2026-09-07 14:16:03.341517+07	\N
39	1	L231Z	82.00	2027-03-15	2026-09-15 14:16:03.360884+07	\N
40	4	L371T	92.00	2027-06-25	2026-09-15 14:16:03.369364+07	\N
42	26	L830L	101.00	2027-02-24	2026-09-15 14:16:03.37602+07	\N
43	11	L548T	145.00	2027-03-09	2026-09-15 14:16:03.387748+07	\N
45	14	L702H	108.00	2026-11-15	2026-09-15 14:16:03.392702+07	\N
46	16	L160H	211.00	2026-12-01	2026-09-15 14:16:03.395702+07	\N
47	21	L626H	68.00	2027-01-24	2026-09-15 14:16:03.400514+07	\N
48	23	L597G	221.00	2027-04-01	2026-09-15 14:16:03.402566+07	\N
49	2	L584Q	250.00	2027-01-01	2026-09-15 14:16:03.406997+07	\N
50	6	L541N	218.00	2027-03-02	2026-09-15 14:16:03.410408+07	\N
51	9	L846B	271.00	2027-05-05	2026-09-15 14:16:03.410408+07	\N
52	3	L287K	158.00	2027-03-12	2026-09-15 14:16:03.420135+07	\N
54	30	L200B	190.00	2027-04-29	2026-09-15 14:16:03.420135+07	\N
5	4	L303Y	43.00	2027-06-16	2026-09-15 14:16:03.430381+07	\N
41	17	L316U	256.00	2027-05-26	2026-09-15 14:16:03.430381+07	\N
8	6	L881M	32.00	2026-10-02	2026-09-12 14:16:03.442058+07	\N
55	31	123	273.00	2028-08-17	2026-09-15 14:36:55.018528+07	\N
56	33	L100V	400.00	2027-10-03	2026-09-15 14:37:11.90167+07	\N
58	23	LO68N	320.00	2026-03-28	2026-09-15 14:37:24.816125+07	\N
59	35	HD1	120.00	\N	2026-09-15 14:52:20.75661+07	\N
60	34	HD1	90.00	2026-10-07	2026-09-15 14:53:03.263147+07	\N
61	37	LO16K	93.00	2027-08-19	2026-09-19 14:00:50.210705+07	\N
62	36	L805D	134.00	2028-08-07	2026-09-19 15:12:05.119491+07	\N
63	40	LOG6P	7.00	2026-10-09	2026-10-04 12:47:04.755474+07	\N
33	26	L880F	0.00	2026-09-23	2026-10-04 12:59:51.746462+07	\N
14	11	L987D	0.00	2026-10-04	2026-10-04 13:01:23.919085+07	\N
13	10	L333L	0.00	2026-09-01	2026-10-04 13:06:31.307894+07	\N
53	10	L177R	273.00	2027-06-08	2026-10-04 13:06:31.308903+07	\N
17	13	L723Y	45.00	2027-03-19	2026-10-04 13:40:38.698378+07	\N
44	13	L165M	0.00	2026-11-19	2026-10-04 13:40:38.696379+07	\N
57	32	L441Z	0.00	2026-07-16	2026-10-04 14:26:06.259625+07	\N
15	12	L954N	8.00	2027-05-14	2026-10-04 14:26:29.008721+07	\N
\.


--
-- Data for Name: inventory_transactions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.inventory_transactions (id, inventory_id, change_qty, transaction_type, reference_type, reference_id, note, created_at) FROM stdin;
1	39	82.00	import	receipt_line	1	\N	2026-09-15 14:16:03.329476+07
2	40	92.00	import	receipt_line	2	\N	2026-09-15 14:16:03.329476+07
3	41	296.00	import	receipt_line	3	\N	2026-09-15 14:16:03.329476+07
4	42	101.00	import	receipt_line	4	\N	2026-09-15 14:16:03.329476+07
5	43	145.00	import	receipt_line	5	\N	2026-09-15 14:16:03.38355+07
6	44	107.00	import	receipt_line	6	\N	2026-09-15 14:16:03.38355+07
7	45	108.00	import	receipt_line	7	\N	2026-09-15 14:16:03.38355+07
8	46	211.00	import	receipt_line	8	\N	2026-09-15 14:16:03.38355+07
9	47	68.00	import	receipt_line	9	\N	2026-09-15 14:16:03.3981+07
10	48	221.00	import	receipt_line	10	\N	2026-09-15 14:16:03.3981+07
11	49	250.00	import	receipt_line	12	\N	2026-09-15 14:16:03.407698+07
12	50	218.00	import	receipt_line	13	\N	2026-09-15 14:16:03.407698+07
13	51	271.00	import	receipt_line	14	\N	2026-09-15 14:16:03.407698+07
14	52	158.00	import	receipt_line	18	\N	2026-09-15 14:16:03.418846+07
15	53	286.00	import	receipt_line	19	\N	2026-09-15 14:16:03.418846+07
16	54	190.00	import	receipt_line	20	\N	2026-09-15 14:16:03.418846+07
17	5	-15.00	export	camera_session	18	Xuất theo đơn khách lẻ	2026-09-15 14:16:03.430381+07
18	41	-40.00	export	camera_session	19	Xuất cho đại lý con	2026-09-15 14:16:03.430381+07
19	33	-6.00	export	manual	\N	Xuất huỷ (bao bì hư)	2026-09-14 14:16:03.430381+07
20	14	-20.00	export	camera_session	20	\N	2026-09-14 14:16:03.436454+07
21	8	-10.00	export	manual	\N	\N	2026-09-12 14:16:03.442058+07
22	55	273.00	import	receipt_line	21	\N	2026-09-15 14:36:54.894184+07
23	56	400.00	import	receipt_line	22	\N	2026-09-15 14:37:11.896344+07
24	57	204.00	import	receipt_line	23	\N	2026-09-15 14:37:17.946736+07
25	58	320.00	import	receipt_line	24	\N	2026-09-15 14:37:24.809375+07
26	59	120.00	import	receipt_line	26	\N	2026-09-15 14:52:20.748248+07
27	60	90.00	import	receipt_line	25	\N	2026-09-15 14:53:03.25873+07
28	61	93.00	import	receipt_line	37	\N	2026-09-19 14:00:50.191729+07
29	62	134.00	import	receipt_line	35	\N	2026-09-19 15:12:05.105857+07
30	44	-20.00	export	camera_session	38	Xuất qua camera, phiên #38	2026-09-30 13:56:14.38954+07
31	63	7.00	import	receipt_line	43	\N	2026-10-04 12:47:04.741124+07
32	33	-9.00	export	camera_session	43	Xuất qua camera, phiên #43	2026-10-04 12:59:51.736227+07
33	14	-2.00	export	camera_session	44	Xuất qua camera, phiên #44	2026-10-04 13:01:23.914355+07
34	13	-11.00	export	camera_session	45	Xuất qua camera, phiên #45	2026-10-04 13:05:49.212544+07
35	53	-1.00	export	camera_session	45	Xuất qua camera, phiên #45	2026-10-04 13:05:49.212544+07
36	13	0.00	export	camera_session	46	Xuất qua camera, phiên #46	2026-10-04 13:06:31.304399+07
37	53	-12.00	export	camera_session	46	Xuất qua camera, phiên #46	2026-10-04 13:06:31.304399+07
38	44	-87.00	export	camera_session	47	Xuất qua camera, phiên #47	2026-10-04 13:40:38.686719+07
39	17	-1.00	export	camera_session	47	Xuất qua camera, phiên #47	2026-10-04 13:40:38.686719+07
40	57	-204.00	export	camera_session	48	Xuất qua camera, phiên #48	2026-10-04 14:26:06.24375+07
41	15	-10.00	export	camera_session	49	Xuất qua camera, phiên #49	2026-10-04 14:26:28.99782+07
\.


--
-- Data for Name: products; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.products (id, sku, name, category, unit, low_stock_threshold, created_at) FROM stdin;
1	SP-001	Sữa tươi Vinamilk 1L	Sữa & đồ uống	thùng	15.00	2026-09-15 14:16:03.329476+07
2	SP-002	Sữa tươi TH True Milk 1L	Sữa & đồ uống	thùng	15.00	2026-09-15 14:16:03.329476+07
3	SP-003	Sữa đặc Ông Thọ	Sữa & đồ uống	thùng	10.00	2026-09-15 14:16:03.329476+07
4	SP-004	Nước suối Lavie 500ml	Sữa & đồ uống	thùng	20.00	2026-09-15 14:16:03.329476+07
5	SP-005	Nước suối Aquafina 500ml	Sữa & đồ uống	thùng	20.00	2026-09-15 14:16:03.329476+07
6	SP-006	Coca-Cola lon 330ml	Sữa & đồ uống	thùng	25.00	2026-09-15 14:16:03.329476+07
7	SP-007	Pepsi lon 330ml	Sữa & đồ uống	thùng	25.00	2026-09-15 14:16:03.329476+07
8	SP-008	Nước tăng lực Sting dâu 330ml	Sữa & đồ uống	thùng	15.00	2026-09-15 14:16:03.329476+07
9	SP-009	Trà xanh không độ	Sữa & đồ uống	thùng	15.00	2026-09-15 14:16:03.329476+07
10	SP-010	Cà phê hòa tan G7 3in1	Sữa & đồ uống	thùng	10.00	2026-09-15 14:16:03.329476+07
11	SP-011	Bánh Oreo hộp 133g	Bánh kẹo	thùng	10.00	2026-09-15 14:16:03.329476+07
12	SP-012	Bánh Cosy quy bơ	Bánh kẹo	thùng	10.00	2026-09-15 14:16:03.329476+07
13	SP-013	Bánh Solite hộp	Bánh kẹo	thùng	10.00	2026-09-15 14:16:03.329476+07
14	SP-014	Kẹo Mentos bạc hà	Bánh kẹo	thùng	12.00	2026-09-15 14:16:03.329476+07
15	SP-015	Kẹo Alpenliebe	Bánh kẹo	thùng	12.00	2026-09-15 14:16:03.329476+07
16	SP-016	Snack Oishi khoai tây	Bánh kẹo	thùng	15.00	2026-09-15 14:16:03.329476+07
17	SP-017	Mì Hảo Hảo tôm chua cay	Thực phẩm khô	thùng	30.00	2026-09-15 14:16:03.329476+07
18	SP-018	Mì Omachi sốt bò hầm	Thực phẩm khô	thùng	25.00	2026-09-15 14:16:03.329476+07
19	SP-019	Cháo gói Kinh Đô	Thực phẩm khô	thùng	15.00	2026-09-15 14:16:03.329476+07
20	SP-020	Gạo ST25 túi 5kg	Thực phẩm khô	bao	10.00	2026-09-15 14:16:03.329476+07
21	SP-021	Dầu ăn Simply 1L	Gia vị	thùng	8.00	2026-09-15 14:16:03.329476+07
22	SP-022	Dầu ăn Neptune 1L	Gia vị	thùng	8.00	2026-09-15 14:16:03.329476+07
23	SP-023	Nước mắm Nam Ngư 500ml	Gia vị	thùng	8.00	2026-09-15 14:16:03.329476+07
24	SP-024	Nước mắm Chinsu 500ml	Gia vị	thùng	8.00	2026-09-15 14:16:03.329476+07
25	SP-025	Hạt nêm Knorr	Gia vị	thùng	10.00	2026-09-15 14:16:03.329476+07
26	SP-026	Bột giặt Omo 3kg	Hoá phẩm	thùng	6.00	2026-09-15 14:16:03.329476+07
27	SP-027	Bột giặt Ariel 3kg	Hoá phẩm	thùng	6.00	2026-09-15 14:16:03.329476+07
28	SP-028	Nước xả Comfort 1.5L	Hoá phẩm	thùng	8.00	2026-09-15 14:16:03.329476+07
29	SP-029	Nước rửa chén Sunlight	Hoá phẩm	thùng	8.00	2026-09-15 14:16:03.329476+07
30	SP-030	Giấy vệ sinh Pulppy 10 cuộn	Hoá phẩm	lốc	10.00	2026-09-15 14:16:03.329476+07
31	\N	Kem đánh răng P/S	\N	thùng	10.00	2026-09-15 14:36:05.679693+07
32	\N	Bánh AFC	\N	thùng	10.00	2026-09-15 14:36:15.235369+07
33	\N	Dầu gội Sunsilk	\N	thùng	10.00	2026-09-15 14:36:25.850362+07
34	\N	Mỳ Hảo Hảo	\N	thùng	10.00	2026-09-15 14:51:19.08868+07
35	\N	Mỳ Gấu Đỏ	\N	thùng	10.00	2026-09-15 14:51:51.757522+07
36	\N	Bánh Oreo	\N	thùng	10.00	2026-09-15 15:12:27.491729+07
37	\N	Mì Kokomi	\N	thùng	10.00	2026-09-15 15:12:33.160104+07
38	\N	Trà Ô Long Tea4	\N	thùng	10.00	2026-09-16 19:32:42.574246+07
39	\N	Nước Aquafina	\N	thùng	10.00	2026-09-22 18:21:03.545366+07
40	\N	Mì Omachi	\N	thùng	10.00	2026-10-04 12:46:31.407131+07
\.


--
-- Data for Name: push_subscriptions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.push_subscriptions (id, endpoint, p256dh, auth, label, created_at) FROM stdin;
\.


--
-- Data for Name: receipt_line_items; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.receipt_line_items (id, receipt_id, line_no, product_name_raw, product_id, quantity, batch_code, expiry_date, match_score, field_confidence, created_at) FROM stdin;
1	1	1	Sữa tươi Vinamilk 1L	1	82.00	L231Z	2027-03-15	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.329476+07
2	1	2	Nước suối Lavie 500ml	4	92.00	L371T	2027-06-25	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.329476+07
3	1	3	Mì Hảo Hảo tôm chua cay	17	296.00	L316U	2027-05-26	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.329476+07
4	1	4	Bột giặt Omo 3kg	26	101.00	L830L	2027-02-24	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.329476+07
5	2	1	Bánh Oreo hộp 133g	11	145.00	L548T	2027-03-09	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.38355+07
6	2	2	Bánh Solite hộp	13	107.00	L165M	2026-11-19	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.38355+07
7	2	3	Kẹo Mentos bạc hà	14	108.00	L702H	2026-11-15	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.38355+07
8	2	4	Snack Oishi khoai tây	16	211.00	L160H	2026-12-01	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.38355+07
9	3	1	Dầu ăn Simply 1L	21	68.00	L626H	2027-01-24	1.0000	\N	2026-09-15 14:16:03.3981+07
10	3	2	Nước mắm Nam Ngư 500ml	23	221.00	L597G	2027-04-01	1.0000	\N	2026-09-15 14:16:03.3981+07
11	3	3	Hạt nêm Knorr	25	83.00	L840V	2027-04-10	1.0000	\N	2026-09-15 14:16:03.3981+07
12	4	1	Sữa tươi TH True Milk 1L	2	250.00	L584Q	2027-01-01	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.407698+07
13	4	2	Coca-Cola lon 330ml	6	218.00	L541N	2027-03-02	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.407698+07
14	4	3	Trà xanh không độ	9	271.00	L846B	2027-05-05	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.407698+07
15	5	1	Mì Omachi sốt bò hầm	18	42.00	L162P	2027-05-19	1.0000	\N	2026-09-15 14:16:03.415711+07
16	5	2	Cháo gói Kinh Đô	19	73.00	L919D	2027-01-16	1.0000	\N	2026-09-15 14:16:03.415711+07
17	5	3	Bột giặt Ariel 3kg	27	54.00	L294U	2027-03-08	1.0000	\N	2026-09-15 14:16:03.415711+07
18	6	1	Sữa đặc Ông Thọ	3	158.00	L287K	2027-03-12	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.418846+07
19	6	2	Cà phê hòa tan G7 3in1	10	286.00	L177R	2027-06-08	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.418846+07
20	6	3	Giấy vệ sinh Pulppy 10 cuộn	30	190.00	L200B	2027-04-29	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:16:03.418846+07
24	8	4	Nước mắm Nam Ngư	23	320.00	LO68N	2026-03-28	0.8421	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:27:24.56371+07
21	8	1	Kem đánh răng P/S	31	273.00	123	2028-08-17	0.3750	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:27:24.56371+07
23	8	3	Bánh AFC	32	204.00	L441Z	2026-07-16	0.3846	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:27:24.56371+07
22	8	2	Dầu gội Sunsilk	33	400.00	L100V	2027-10-03	0.5161	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 14:27:24.56371+07
25	9	1	Mỳ Hảo Hảo	34	100.00	HD1	2026-10-07	1.0000	\N	2026-09-15 14:51:30.162394+07
26	9	2	Mỳ Gấu Đỏ	35	120.00	HD1	\N	\N	\N	2026-09-15 14:51:46.427036+07
28	10	2	Bánh Solite	13	343.00	L45OW	2026-03-31	0.8462	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 15:12:10.911693+07
30	10	4	Dầu gội Sunsilk	33	202.00	LO15X	2026-07-05	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 15:12:10.911693+07
27	10	1	Bánh Oreo	36	134.00	L805D	2028-08-07	0.6667	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 15:12:10.911693+07
40	13	2	Mì Omachi	\N	38.00	L1371	2027-01-04	0.6207	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-22 18:20:31.975708+07
29	10	3	Mì Kokomi	37	24.00	LO16K	2027-08-19	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-15 15:12:10.911693+07
31	11	1	Bột giặt Ariel	27	271.00	L1671	2027-10-13	0.8750	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-16 19:32:06.092449+07
33	11	3	Snack Oishi	\N	150.00	L606Z	2027-12-26	0.6875	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-16 19:32:06.092449+07
34	11	4	Bánh Solite	13	208.00	L157Z	2028-07-15	0.8462	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-16 19:32:06.092449+07
32	11	2	Trà Ô Long Tea4	38	212.00	L222X	2028-10-15	0.3590	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-16 19:32:06.092449+07
35	12	1	Bánh Oreo	36	134.00	L805D	2028-08-07	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-19 14:00:13.364975+07
36	12	2	Bánh Solite	13	343.00	L45OW	2026-03-31	0.8462	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-19 14:00:13.364975+07
37	12	3	Mì Kokomi	37	93.00	LO16K	2027-08-19	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-19 14:00:13.364975+07
38	12	4	Dầu gội Sunsilk	33	202.00	LO15X	2026-07-05	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-19 14:00:13.364975+07
41	13	3	Đường Biên Hòa	\N	132.00	L404Q	2027-08-03	0.3889	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-22 18:20:31.975708+07
42	13	4	Nước mắm Nam Ngư	23	138.00	L769G	2027-09-16	0.8421	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-22 18:20:31.975708+07
39	13	1	Nước Aquafina	39	38.00	L613P	2027-04-17	0.7027	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-09-22 18:20:31.975708+07
44	14	2	Cà phê G7	\N	260.00	L288Y	2028-10-14	0.5806	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-10-04 12:46:05.66426+07
45	14	3	Coca Cola 390ml	6	305.00	L343Q	2027-04-29	0.7647	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-10-04 12:46:05.66426+07
46	14	4	Sữa Vinamilk 180ml	\N	66.00	LO7ER	2026-05-02	0.7368	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-10-04 12:46:05.66426+07
47	14	5	Dầu gội Sunsilk	33	399.00	L662X	2027-05-15	1.0000	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-10-04 12:46:05.66426+07
43	14	1	Mì Omachi	40	7.00	LOG6P	2026-10-09	0.6207	{"batch": 1.0, "expiry": 1.0, "quantity": 1.0}	2026-10-04 12:46:05.66426+07
\.


--
-- Data for Name: reconciliations; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.reconciliations (id, receipt_id, receipt_line_item_id, product_id, session_id, receipt_total, camera_total, difference, threshold_used, status, resolved_by, resolved_note, resolved_at, created_at) FROM stdin;
1	1	1	1	1	82.00	82	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.329476+07
2	1	2	4	2	92.00	92	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.329476+07
3	1	3	17	3	296.00	296	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.329476+07
4	1	4	26	4	101.00	101	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.329476+07
5	2	5	11	5	145.00	145	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.38355+07
6	2	6	13	6	107.00	107	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.38355+07
7	2	7	14	7	108.00	108	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.38355+07
8	2	8	16	8	211.00	211	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.38355+07
9	3	9	21	9	68.00	68	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.3981+07
10	3	10	23	10	221.00	221	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.3981+07
11	3	11	25	11	83.00	53	-30.00	0.0200	flagged	\N	\N	\N	2026-09-15 14:16:03.3981+07
12	4	12	2	12	250.00	250	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.407698+07
13	4	13	6	13	218.00	218	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.407698+07
14	4	14	9	14	271.00	271	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.407698+07
15	6	18	3	15	158.00	158	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.418846+07
16	6	19	10	16	286.00	286	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.418846+07
17	6	20	30	17	190.00	190	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:16:03.418846+07
18	8	21	31	21	273.00	273	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:36:54.894184+07
19	8	22	33	22	400.00	400	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:37:11.896344+07
20	8	23	32	23	204.00	204	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:37:17.946736+07
21	8	24	23	24	320.00	320	0.00	0.0200	matched	\N	\N	\N	2026-09-15 14:37:24.809375+07
23	9	26	35	27	120.00	119	-1.00	0.0200	matched	\N	\N	\N	2026-09-15 14:52:20.748248+07
22	9	25	34	26	100.00	90	-10.00	0.0200	resolved_override	\N	đã kiểm lại bằng tay, số camera đúng	2026-09-15 14:53:03.260144+07	2026-09-15 14:52:07.314188+07
24	10	29	37	28	24.00	35	11.00	0.0000	flagged	\N	\N	\N	2026-09-15 15:17:43.449529+07
25	10	29	37	30	24.00	35	11.00	0.0000	flagged	\N	\N	\N	2026-09-15 15:36:32.923069+07
26	12	37	37	32	93.00	93	0.00	0.0000	matched	\N	\N	\N	2026-09-19 14:00:50.191729+07
27	12	35	36	33	134.00	35	-99.00	0.0000	flagged	\N	\N	\N	2026-09-19 15:06:57.678293+07
28	12	35	36	34	134.00	21	-113.00	0.0000	flagged	\N	\N	\N	2026-09-19 15:08:36.540175+07
29	12	35	36	36	134.00	134	0.00	0.0000	matched	\N	\N	\N	2026-09-19 15:12:05.105857+07
30	13	39	39	37	38.00	25	-13.00	0.0000	flagged	\N	\N	\N	2026-09-22 18:21:20.970113+07
31	\N	\N	13	38	20.00	20	0.00	0.0000	matched	\N	\N	\N	2026-09-30 13:56:14.38954+07
32	14	43	40	39	7.00	5	-2.00	0.0000	flagged	\N	\N	\N	2026-10-04 12:46:52.562462+07
33	14	43	40	40	7.00	7	0.00	0.0000	matched	\N	\N	\N	2026-10-04 12:47:04.741124+07
34	14	45	6	41	305.00	35	-270.00	0.0000	flagged	\N	\N	\N	2026-10-04 12:48:43.407656+07
35	14	47	33	42	399.00	17	-382.00	0.0000	flagged	\N	\N	\N	2026-10-04 12:50:26.876461+07
36	\N	\N	26	43	9.00	9	0.00	0.0000	matched	\N	\N	\N	2026-10-04 12:59:51.736227+07
37	\N	\N	11	44	2.00	2	0.00	0.0000	matched	\N	\N	\N	2026-10-04 13:01:23.914355+07
38	\N	\N	10	45	12.00	12	0.00	0.0000	matched	\N	\N	\N	2026-10-04 13:05:49.212544+07
39	\N	\N	10	46	12.00	12	0.00	0.0000	matched	\N	\N	\N	2026-10-04 13:06:31.304399+07
40	\N	\N	13	47	88.00	88	0.00	0.0000	matched	\N	\N	\N	2026-10-04 13:40:38.686719+07
41	\N	\N	32	48	204.00	204	0.00	0.0000	matched	\N	\N	\N	2026-10-04 14:26:06.24375+07
42	\N	\N	12	49	10.00	10	0.00	0.0000	matched	\N	\N	\N	2026-10-04 14:26:28.99782+07
\.


--
-- Name: alerts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.alerts_id_seq', 32, true);


--
-- Name: camera_count_sessions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.camera_count_sessions_id_seq', 49, true);


--
-- Name: import_receipts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.import_receipts_id_seq', 14, true);


--
-- Name: inventory_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.inventory_id_seq', 63, true);


--
-- Name: inventory_transactions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.inventory_transactions_id_seq', 41, true);


--
-- Name: products_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.products_id_seq', 40, true);


--
-- Name: push_subscriptions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.push_subscriptions_id_seq', 1, false);


--
-- Name: receipt_line_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.receipt_line_items_id_seq', 47, true);


--
-- Name: reconciliations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.reconciliations_id_seq', 42, true);


--
-- Name: alerts alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_pkey PRIMARY KEY (id);


--
-- Name: camera_count_sessions camera_count_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.camera_count_sessions
    ADD CONSTRAINT camera_count_sessions_pkey PRIMARY KEY (id);


--
-- Name: camera_count_sessions camera_count_sessions_session_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.camera_count_sessions
    ADD CONSTRAINT camera_count_sessions_session_code_key UNIQUE (session_code);


--
-- Name: import_receipts import_receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.import_receipts
    ADD CONSTRAINT import_receipts_pkey PRIMARY KEY (id);


--
-- Name: import_receipts import_receipts_receipt_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.import_receipts
    ADD CONSTRAINT import_receipts_receipt_code_key UNIQUE (receipt_code);


--
-- Name: inventory inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_pkey PRIMARY KEY (id);


--
-- Name: inventory inventory_product_id_batch_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_product_id_batch_code_key UNIQUE (product_id, batch_code);


--
-- Name: inventory_transactions inventory_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_transactions
    ADD CONSTRAINT inventory_transactions_pkey PRIMARY KEY (id);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: products products_sku_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_sku_key UNIQUE (sku);


--
-- Name: push_subscriptions push_subscriptions_endpoint_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_endpoint_key UNIQUE (endpoint);


--
-- Name: push_subscriptions push_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: receipt_line_items receipt_line_items_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.receipt_line_items
    ADD CONSTRAINT receipt_line_items_pkey PRIMARY KEY (id);


--
-- Name: reconciliations reconciliations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reconciliations
    ADD CONSTRAINT reconciliations_pkey PRIMARY KEY (id);


--
-- Name: idx_alerts_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_alerts_status ON public.alerts USING btree (status);


--
-- Name: idx_camera_sessions_receipt; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_camera_sessions_receipt ON public.camera_count_sessions USING btree (linked_receipt_id);


--
-- Name: idx_inv_txn_inventory; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_inv_txn_inventory ON public.inventory_transactions USING btree (inventory_id);


--
-- Name: idx_inventory_expiry; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_inventory_expiry ON public.inventory USING btree (expiry_date);


--
-- Name: idx_line_items_receipt; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_line_items_receipt ON public.receipt_line_items USING btree (receipt_id);


--
-- Name: idx_receipts_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_receipts_status ON public.import_receipts USING btree (status);


--
-- Name: alerts alerts_inventory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_inventory_id_fkey FOREIGN KEY (inventory_id) REFERENCES public.inventory(id);


--
-- Name: alerts alerts_reconciliation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_reconciliation_id_fkey FOREIGN KEY (reconciliation_id) REFERENCES public.reconciliations(id);


--
-- Name: camera_count_sessions camera_count_sessions_linked_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.camera_count_sessions
    ADD CONSTRAINT camera_count_sessions_linked_receipt_id_fkey FOREIGN KEY (linked_receipt_id) REFERENCES public.import_receipts(id);


--
-- Name: camera_count_sessions camera_count_sessions_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.camera_count_sessions
    ADD CONSTRAINT camera_count_sessions_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: camera_count_sessions camera_count_sessions_receipt_line_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.camera_count_sessions
    ADD CONSTRAINT camera_count_sessions_receipt_line_item_id_fkey FOREIGN KEY (receipt_line_item_id) REFERENCES public.receipt_line_items(id);


--
-- Name: inventory inventory_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: inventory_transactions inventory_transactions_inventory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_transactions
    ADD CONSTRAINT inventory_transactions_inventory_id_fkey FOREIGN KEY (inventory_id) REFERENCES public.inventory(id);


--
-- Name: receipt_line_items receipt_line_items_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.receipt_line_items
    ADD CONSTRAINT receipt_line_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: receipt_line_items receipt_line_items_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.receipt_line_items
    ADD CONSTRAINT receipt_line_items_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.import_receipts(id) ON DELETE CASCADE;


--
-- Name: reconciliations reconciliations_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reconciliations
    ADD CONSTRAINT reconciliations_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: reconciliations reconciliations_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reconciliations
    ADD CONSTRAINT reconciliations_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.import_receipts(id);


--
-- Name: reconciliations reconciliations_receipt_line_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reconciliations
    ADD CONSTRAINT reconciliations_receipt_line_item_id_fkey FOREIGN KEY (receipt_line_item_id) REFERENCES public.receipt_line_items(id);


--
-- Name: reconciliations reconciliations_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reconciliations
    ADD CONSTRAINT reconciliations_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.camera_count_sessions(id);


--
-- PostgreSQL database dump complete
--

\unrestrict RJVxGeeqcrPSGa9p5dYZ2a98lux2p5n5F0b2PCjaGKMrLDNlfnxrALckGm8XNK3

