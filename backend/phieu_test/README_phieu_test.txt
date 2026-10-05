PHIẾU NHẬP DÙNG ĐỂ TEST — nội dung ĐÚNG của từng ảnh (để đối chiếu với kết quả OCR)
Ngày nhập trên phiếu: 05/10/2026.  Cột: Tên sản phẩm | Số lượng | Mã lô | HSD
Cách thử: Nhập kho -> '+ Quét phiếu mới' -> chọn ảnh -> xem kết quả OCR -> sửa dòng sai -> đếm.

=== phieu_test_01_de_doc.png  (kiểu: clean, Nhà phân phối Sài Gòn Food)
Mục đích : Phiếu DỄ NHẤT: ảnh sạch, tên sản phẩm đúng 100% như danh mục. Dùng để thử luồng cơ bản: quét -> kiểm tra dòng -> đếm camera -> cộng kho.
Mong đợi : Cả 4 dòng đọc đúng và tự gán đúng sản phẩm; phiếu ở trạng thái 'Chờ đếm hàng'.
Nội dung đúng:
    Mì Hảo Hảo tôm chua cay                    40   L412A   04/03/2027
    Mì Omachi sốt bò hầm                       24   L413B   22/02/2027
    Mì Kokomi tôm chua cay                     20   L414C   27/02/2027
    Phở bò ăn liền Vifon                       12   L415D   02/02/2027

=== phieu_test_02_anh_chup.jpg  (kiểu: photo, Đại lý Nước giải khát Minh Phát)
Mục đích : Giống ảnh chụp điện thoại: tờ phiếu nằm trên bàn, hơi nghiêng, hơi nhiễu. Tên sản phẩm đúng.
Mong đợi : Đọc được cả 5 dòng; có thể có 1-2 ô số/mã lô đọc nhầm — hãy sửa tay ở bước kiểm tra dòng.
Nội dung đúng:
    Nước suối Lavie 500ml                      30   L521M   27/05/2028
    Nước suối Aquafina 500ml                   30   L522N   17/05/2028
    Coca-Cola lon 330ml                        24   L523P   01/08/2027
    Pepsi lon 330ml                            24   L524Q   11/08/2027
    Trà xanh không độ 455ml                    12   L525R   12/07/2027

=== phieu_test_03_ten_khong_dau.png  (kiểu: clean, Công ty TNHH Gia vị Việt Tín)
Mục đích : Tên sản phẩm VIẾT KHÔNG DẤU / IN HOA / RÚT GỌN — để thử so khớp gần đúng với danh mục (ngưỡng khớp 0,75) và các nút 'Gợi ý từ danh mục'.
Mong đợi : Dự đoán (tính bằng đúng hàm so khớp của dự án trên danh mục seed): chỉ 'Nuoc mam Chinsu 500ml' tự gán; 3 dòng còn lại 'chưa gán SP' (điểm khớp 0,36-0,64 < 0,75) — gán bằng ô chọn sản phẩm hoặc nút '💡 Gợi ý từ danh mục'.
Nội dung đúng:
    DAU AN SIMPLY 1L                           12   L631E   28/01/2028
    Nuoc mam Chinsu 500ml                      10   L632F   16/07/2028
    HAT NEM KNORR THIT THAN 900G                8   L633G   06/07/2028
    Duong cat trang Bien Hoa 1kg               20   L634H   27/05/2028

=== phieu_test_04_co_san_pham_moi.png  (kiểu: clean, Công ty CP Thương mại Hưng Thịnh)
Mục đích : Có 2 sản phẩm CHƯA CÓ trong danh mục (7Up, Hura Swiss Roll) — để thử nút '+ Tạo sản phẩm mới từ tên …' và luồng gán sản phẩm trước khi đếm.
Mong đợi : Dự đoán: 7Up và Hura 'chưa gán SP' (điểm khớp 0,58 và 0,62); Alpenliebe và Oreo tự gán (1,00). Phải gán hoặc tạo sản phẩm cho 2 dòng đầu rồi mới đếm được.
Nội dung đúng:
    Nước ngọt 7Up lon 330ml                    24   L741J   21/08/2027
    Bánh Hura Swiss Roll hộp                   10   L742K   14/03/2027
    Kẹo Alpenliebe                             15   L743L   17/02/2028
    Bánh Oreo hộp 133g                         12   L744M   12/06/2027

=== phieu_test_05_dai_8_dong.jpg  (kiểu: photo, Chành hoá phẩm Phú Lộc)
Mục đích : Phiếu DÀI 8 dòng, ảnh chụp: thử danh sách phiếu ('+N sản phẩm khác'), đếm lần lượt nhiều loại hàng.
Mong đợi : Đọc được 8 dòng (có thể sai vài ô); thẻ phiếu trong danh sách hiện 3 dòng đầu + '+5 sản phẩm khác'.
Nội dung đúng:
    Bột giặt Omo 3kg                           12   L851A   01/07/2029
    Bột giặt Ariel 3kg                         10   L852B   01/07/2029
    Nước xả Comfort 1.5L                        8   L853C   11/06/2029
    Nước rửa chén Sunlight 750g                12   L854D   21/06/2029
    Nước lau sàn Sunlight 1L                    6   L855E   01/06/2029
    Dầu gội Clear men 630g                      6   L856F   01/07/2029
    Sữa tắm Lifebuoy 850g                       6   L857G   26/06/2029
    Kem đánh răng P/S 230g                     20   L858H   20/08/2029

=== phieu_test_06_mo_toi.jpg  (kiểu: dark, Công ty TNHH Phân phối An Bình)
Mục đích : Ảnh THIẾU SÁNG, hơi nhoè, nghiêng nhiều — trường hợp xấu. Thử cách ứng dụng xử lý khi OCR đọc kém (điểm tin cậy thấp, thiếu dòng, đọc sai).
Mong đợi : Rất có thể đọc sai/thiếu vài ô hoặc cả phiếu bị đánh dấu lỗi OCR — đó là kết quả bình thường của ca khó này.
Nội dung đúng:
    Sữa tươi Vinamilk 100% có đường 1L         24   L961S   02/02/2027
    Sữa tươi TH True Milk ít đường 1L          18   L962T   04/03/2027
    Sữa đặc Ông Thọ lon 380g                   10   L963U   17/02/2028
