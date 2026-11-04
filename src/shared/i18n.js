/* Shared i18n + theme bootstrap. SHARED FILE - do not edit without telling the team.
 *
 * Load it in <head> (before paint) on every page:  <script src="/shared/i18n.js"></script>
 *
 *   Markup:   <h1 data-i18n="page.findHub.title"></h1>
 *             <input data-i18n-attr="placeholder:common.search,aria-label:common.search">
 *   Script:   I18n.t('hub.free', { n: 3 })      -> translated string
 *             I18n.hubName(hub)                  -> localized Hub name (by id, falls back to API name)
 *             document.addEventListener('langchange', redraw)
 *
 * Add new strings to BOTH dictionaries (en and vi). Missing keys fall back to English, then to the key.
 */
const I18n = (() => {
  const LS_LANG = 'hub_lang', LS_THEME = 'hub_theme';
  const SUPPORTED = ['en', 'vi'];

  const DICT = {
    en: {
      'app.name': 'Smart E-Mobility Hub',
      'app.tagline': 'Electric mobility coordination for the VNU-HCM Urban Area',
      'app.mvp': 'MVP · simulated data',
      'common.skip': 'Skip to main content',
      'common.loading': 'Loading…',
      'common.error': 'Error',
      'common.notImplemented': 'Not implemented yet',
      'common.owner': 'Owner',
      'common.useCase': 'Use case',
      'common.useCases': 'Use cases',
      'common.logout': 'Log out',
      'common.language': 'Language',
      'common.theme': 'Toggle dark mode',
      'common.themeLight': 'Switch to light mode',
      'common.themeDark': 'Switch to dark mode',
      'common.mainNav': 'Main navigation',
      'common.retry': 'Try again',
      'common.pending': 'This feature is being built by the team. The raw API response is shown below so you can see it is wired up.',
      'role.student': 'Student',
      'role.operator': 'Operator',
      'menu.findHub': 'Find Hub & Vehicle',
      'menu.reserve': 'Reserve Vehicle / Parking',
      'menu.trips': 'My Trips',
      'menu.charging': 'Charging',
      'menu.wallet': 'Wallet',
      'menu.dashboard': 'Dashboard',
      'menu.incidents': 'Incidents',
      'menu.stations': 'Charging Stations',
      'menu.whatIf': 'What-if',
      'home.loginTitle': 'Try the demo',
      'home.loginDesc': 'Pick a demo account. No password needed — accounts come from configs/hubs-data.json.',
      'home.studentShared': 'Student',
      'home.studentSharedDesc': 'Find, reserve and ride shared electric vehicles.',
      'home.studentEv': 'Student with a private EV',
      'home.studentEvDesc': 'Park and charge your own e-bike or scooter.',
      'home.operator': 'Operator',
      'home.operatorDesc': 'Monitor the network, handle incidents, run What-if scenarios.',
      'home.loginFailed': 'Could not sign in. Is the backend running?',
      'home.overview': 'Hub Overview',
      'home.overviewDesc': 'Live occupancy of every Mobility Hub.',
      'hub.full': '% full',
      'hub.nearFull': 'Nearly full',
      'hub.spaces': 'Free spaces',
      'hub.vehicles': 'Vehicles available',
      'hub.chargers': 'Free charging points',
      'hub.utilization': 'Utilization',
      'page.findHub.title': 'Find Hub & Vehicle',
      'page.findHub.desc': 'Hub map/list, available vehicles, battery %, free parking spaces. Filters: vehicle type, minimum battery, origin/destination Hub.',
      'page.reserve.title': 'Reserve Vehicle / Parking',
      'page.reserve.desc': 'Reserve a vehicle or a parking space, cancel, scan a QR code to pick up, return the vehicle, report an issue.',
      'page.trips.title': 'My Trips',
      'page.trips.desc': 'Your reservations, the active trip and history, with cancel / return / report-issue actions.',
      'page.chargingReq.title': 'Charging Request',
      'page.chargingReq.desc': 'Submit a charging request, pick a charging point, get smart suggestions, cancel and track progress (queue position, ETA).',
      'page.dashboard.title': 'Network Dashboard',
      'page.dashboard.desc': 'Network-wide KPIs, Hub utilization, map markers, alerts, redistribution proposals and relocation orders.',
      'page.incidents.title': 'Incident Handling',
      'page.incidents.desc': 'Incident list with a Handle action: put the device into maintenance, create a ticket, cancel affected reservations.',
      'page.chargingOps.title': 'Charging Stations & Scheduling',
      'page.chargingOps.desc': 'Charging-point status, run prioritization, view the queue and priority scores, manual override.',
      'page.whatIf.title': 'What-if Simulation',
      'page.whatIf.desc': 'Pick a template or enter scenario parameters, run the simulation, view per-Hub impact and recommendations, export a report.',
      'hubname.HUB-METRO': 'VNU-HCM Metro Station',
      'hubname.HUB-KTX': 'Dormitory Zone A',
      'hubname.HUB-CAMPUS': 'University Campus',
      'hubname.HUB-LIB': 'Central Library',
      'filter.allTypes': 'All vehicle types',
      'filter.bike': 'E-Bike',
      'filter.scooter': 'E-Scooter',
      'filter.motorcycle': 'E-Motorcycle',
      'filter.minBattery': 'Min Battery',
      'filter.fromHub': 'Origin Hub',
      'filter.allHubs': 'All Hubs',
      'filter.apply': 'Filter',
      'filter.reset': 'Reset',
      'map.title': 'Interactive Campus Hub Map',
      'map.highAvail': 'Available (>30%)',
      'map.lowAvail': 'Limited (<30%)',
      'map.full': 'Full (0 free)',
      'vehicle.reserveBtn': 'Reserve Vehicle',
      'vehicle.parkBtn': 'Reserve Dock',
      'vehicle.range': 'Est. range',
      'vehicle.battery': 'Battery',
      'vehicle.noVehicles': 'No available shared vehicles matching criteria.',
      'hub.privateEvSection': 'Private EV Parking & Charging Points',
      'hub.sharedFleetSection': 'Available Shared Fleet',
      'hub.freeDocks': 'Available docks',
      'reserve.tabVehicle': 'Shared Vehicle (U2)',
      'reserve.tabParking': 'Parking / Return Dock (U3)',
      'reserve.selectHub': 'Departure Hub',
      'reserve.selectDestHub': 'Destination Hub',
      'reserve.selectVehicle': 'Select Vehicle',
      'reserve.anyVehicle': 'Best available vehicle (Auto)',
      'reserve.parkingMode': 'Reservation Type',
      'reserve.modeShared': 'Shared Return Dock Hold (15-20 min)',
      'reserve.modePrivate': 'Private EV Parking Space',
      'reserve.duration': 'Duration',
      'reserve.depositNotice': 'Refundable Security Deposit: 50,000 VND (held for 15 minutes)',
      'reserve.depositDesc': 'Deposit will be refunded upon return after rental fee deduction.',
      'reserve.btnConfirmVehicle': 'Confirm & Pay Deposit (50,000 VND)',
      'reserve.btnConfirmParking': 'Confirm Dock Reservation',
      'reserve.passTitle': 'Active Reservation Pass',
      'reserve.holdTimer': 'Expires in',
      'reserve.pickupBtn': 'Scan QR to Unlock',
      'reserve.cancelBtn': 'Cancel Reservation',
      'reserve.cancelConfirm': 'Cancel reservation? The 50,000 VND deposit will be fully refunded.',
      'reserve.success': 'Reservation created successfully!',
      'trip.activeTitle': 'Active Trip',
      'trip.rideTime': 'Ride duration',
      'trip.startedAt': 'Started at',
      'trip.from': 'From Hub',
      'trip.returnBtn': 'End Trip & Return Vehicle',
      'trip.reportBtn': 'Report Issue',
      'trip.selectReturnHub': 'Select Return Hub',
      'trip.confirmReturn': 'Confirm Dock & Return',
      'trip.invoiceTitle': 'Trip Invoice & Receipt',
      'trip.durationLabel': 'Ride duration',
      'trip.feeLabel': 'Rental fee charged',
      'trip.refundLabel': 'Deposit refunded',
      'trip.closeReceipt': 'Close Receipt',
      'issue.title': 'Report Breakdown / Issue',
      'issue.target': 'Target Resource',
      'issue.category': 'Category',
      'issue.catBrake': 'Brake Failure',
      'issue.catBattery': 'Battery Danger / Overheating',
      'issue.catTire': 'Flat Tire',
      'issue.catDock': 'Smart Dock Jam',
      'issue.catOther': 'Other Issue',
      'issue.desc': 'Description',
      'issue.submit': 'Submit Issue',
      'issue.success': 'Issue reported successfully! Ticket ID: ',
      'trip.historyTitle': 'Trip History',
      'trip.noHistory': 'No completed trips yet.',
      'trip.noActive': 'No active trip at the moment.',
      'trip.activeReservations': 'Active Reservations',
    },
    vi: {
      'app.name': 'Smart E-Mobility Hub',
      'app.tagline': 'Điều phối phương tiện điện trong Khu đô thị ĐHQG-HCM',
      'app.mvp': 'MVP · dữ liệu giả lập',
      'common.skip': 'Bỏ qua, đến nội dung chính',
      'common.loading': 'Đang tải…',
      'common.error': 'Lỗi',
      'common.notImplemented': 'Chưa hoàn thành',
      'common.owner': 'Phụ trách',
      'common.useCase': 'Use case',
      'common.useCases': 'Use case',
      'common.logout': 'Đăng xuất',
      'common.language': 'Ngôn ngữ',
      'common.theme': 'Bật/tắt chế độ tối',
      'common.themeLight': 'Chuyển sang chế độ sáng',
      'common.themeDark': 'Chuyển sang chế độ tối',
      'common.mainNav': 'Điều hướng chính',
      'common.retry': 'Thử lại',
      'common.pending': 'Tính năng này đang được nhóm xây dựng. Bên dưới là phản hồi API thô để bạn thấy trang đã được nối với backend.',
      'role.student': 'Sinh viên',
      'role.operator': 'Operator',
      'menu.findHub': 'Tìm Hub & xe',
      'menu.reserve': 'Đặt xe / chỗ đỗ',
      'menu.trips': 'Chuyến của tôi',
      'menu.charging': 'Sạc xe',
      'menu.wallet': 'Ví điện tử',
      'menu.dashboard': 'Dashboard',
      'menu.incidents': 'Sự cố',
      'menu.stations': 'Trạm sạc',
      'menu.whatIf': 'What-if',
      'home.loginTitle': 'Dùng thử bản demo',
      'home.loginDesc': 'Chọn một tài khoản demo. Không cần mật khẩu — tài khoản lấy từ configs/hubs-data.json.',
      'home.studentShared': 'Sinh viên',
      'home.studentSharedDesc': 'Tìm, đặt và đi xe điện dùng chung.',
      'home.studentEv': 'Sinh viên có xe điện cá nhân',
      'home.studentEvDesc': 'Gửi và sạc xe đạp/xe máy điện của riêng bạn.',
      'home.operator': 'Operator',
      'home.operatorDesc': 'Giám sát mạng lưới, xử lý sự cố, chạy kịch bản What-if.',
      'home.loginFailed': 'Không đăng nhập được. Backend đã chạy chưa?',
      'home.overview': 'Tổng quan các Hub',
      'home.overviewDesc': 'Tình trạng thời gian thực của từng Mobility Hub.',
      'hub.full': '% đầy',
      'hub.nearFull': 'Gần đầy',
      'hub.spaces': 'Chỗ đỗ trống',
      'hub.vehicles': 'Xe sẵn sàng',
      'hub.chargers': 'Cổng sạc trống',
      'hub.utilization': 'Mức sử dụng',
      'page.findHub.title': 'Tìm Hub & phương tiện',
      'page.findHub.desc': 'Bản đồ/danh sách Hub, xe còn trống, % pin, chỗ đỗ trống. Bộ lọc: loại xe, pin tối thiểu, Hub đi/đến.',
      'page.reserve.title': 'Đặt xe / chỗ đỗ',
      'page.reserve.desc': 'Đặt xe hoặc chỗ đỗ, hủy đặt, quét QR nhận xe, trả xe, báo sự cố.',
      'page.trips.title': 'Chuyến của tôi',
      'page.trips.desc': 'Danh sách đặt chỗ, chuyến đang chạy và lịch sử; có nút hủy / trả xe / báo sự cố.',
      'page.chargingReq.title': 'Đăng ký sạc xe',
      'page.chargingReq.desc': 'Gửi yêu cầu sạc, chọn cổng sạc, xem gợi ý thông minh, hủy và theo dõi tiến độ (vị trí hàng đợi, ETA).',
      'page.dashboard.title': 'Dashboard mạng lưới',
      'page.dashboard.desc': 'KPI toàn mạng, độ đầy của Hub, marker bản đồ, cảnh báo, đề xuất điều phối và lệnh điều chuyển.',
      'page.incidents.title': 'Xử lý sự cố',
      'page.incidents.desc': 'Danh sách sự cố với nút Xử lý: đưa thiết bị vào bảo trì, tạo ticket, hủy đặt chỗ liên quan.',
      'page.chargingOps.title': 'Trạm sạc & lịch sạc',
      'page.chargingOps.desc': 'Trạng thái cổng sạc, chạy lịch ưu tiên, xem hàng đợi và điểm ưu tiên, ghi đè thủ công.',
      'page.whatIf.title': 'Mô phỏng What-if',
      'page.whatIf.desc': 'Chọn mẫu hoặc nhập tham số kịch bản, chạy mô phỏng, xem tác động từng Hub và khuyến nghị, xuất báo cáo.',
      'hubname.HUB-METRO': 'Ga Metro ĐHQG',
      'hubname.HUB-KTX': 'Ký túc xá Khu A',
      'hubname.HUB-CAMPUS': 'Khu trường Đại học',
      'hubname.HUB-LIB': 'Thư viện trung tâm',
      'filter.allTypes': 'Tất cả loại xe',
      'filter.bike': 'Xe đạp điện',
      'filter.scooter': 'Xe scooter điện',
      'filter.motorcycle': 'Xe máy điện',
      'filter.minBattery': 'Mức pin tối thiểu',
      'filter.fromHub': 'Hub xuất phát',
      'filter.allHubs': 'Tất cả Hub',
      'filter.apply': 'Lọc',
      'filter.reset': 'Đặt lại',
      'map.title': 'Bản đồ số hóa khuôn viên ĐHQG',
      'map.highAvail': 'Nhiều xe/chỗ (>30%)',
      'map.lowAvail': 'Sắp hết (<30%)',
      'map.full': 'Đã đầy (0 chỗ)',
      'vehicle.reserveBtn': 'Đặt xe này',
      'vehicle.parkBtn': 'Giữ dock trả xe',
      'vehicle.range': 'Tầm di chuyển',
      'vehicle.battery': 'Mức pin',
      'vehicle.noVehicles': 'Không có xe dùng chung nào tại Hub này phù hợp bộ lọc.',
      'hub.privateEvSection': 'Chỗ đỗ xe điện cá nhân & Cổng sạc',
      'hub.sharedFleetSection': 'Đội xe điện dùng chung',
      'hub.freeDocks': 'Dock trả xe còn trống',
      'reserve.tabVehicle': 'Đặt xe dùng chung (U2)',
      'reserve.tabParking': 'Giữ chỗ đỗ / Dock trả xe (U3)',
      'reserve.selectHub': 'Hub xuất phát',
      'reserve.selectDestHub': 'Hub đích đến',
      'reserve.selectVehicle': 'Chọn xe',
      'reserve.anyVehicle': 'Tự động chọn xe tốt nhất',
      'reserve.parkingMode': 'Mục đích giữ chỗ',
      'reserve.modeShared': 'Giữ dock trả xe dùng chung (15-20 phút)',
      'reserve.modePrivate': 'Chỗ đỗ cho xe cá nhân',
      'reserve.duration': 'Thời gian đỗ',
      'reserve.depositNotice': 'Tiền cọc giữ xe (hoàn lại): 50,000 VNĐ (giữ trong 15 phút)',
      'reserve.depositDesc': 'Tiền cọc sẽ được hoàn lại tự động sau khi trả xe và khấu trừ cước.',
      'reserve.btnConfirmVehicle': 'Xác nhận & Đặt cọc (50,000 VNĐ)',
      'reserve.btnConfirmParking': 'Xác nhận giữ chỗ đỗ',
      'reserve.passTitle': 'Thẻ đặt chỗ điện tử',
      'reserve.holdTimer': 'Hết hạn sau',
      'reserve.pickupBtn': 'Quét QR để mở khóa',
      'reserve.cancelBtn': 'Hủy đặt chỗ',
      'reserve.cancelConfirm': 'Bạn có chắc chắn muốn hủy? Tiền cọc 50,000 VNĐ sẽ được hoàn lại 100%.',
      'reserve.success': 'Đặt chỗ thành công!',
      'trip.activeTitle': 'Chuyến đi đang diễn ra',
      'trip.rideTime': 'Thời gian đi',
      'trip.startedAt': 'Bắt đầu lúc',
      'trip.from': 'Từ Hub',
      'trip.returnBtn': 'Kết thúc chuyến & Trả xe',
      'trip.reportBtn': 'Báo cáo sự cố',
      'trip.selectReturnHub': 'Chọn Hub trả xe',
      'trip.confirmReturn': 'Xác nhận cắm dock & Trả xe',
      'trip.invoiceTitle': 'Hóa đơn chuyến đi',
      'trip.durationLabel': 'Thời gian sử dụng',
      'trip.feeLabel': 'Cước phí thuê',
      'trip.refundLabel': 'Tiền cọc hoàn trả',
      'trip.closeReceipt': 'Đóng',
      'issue.title': 'Báo cáo sự cố phương tiện / trạm',
      'issue.target': 'Đối tượng gặp sự cố',
      'issue.category': 'Phân loại lỗi',
      'issue.catBrake': 'Hỏng phanh',
      'issue.catBattery': 'Lỗi pin / Nguy cơ quá nhiệt',
      'issue.catTire': 'Thủng lốp',
      'issue.catDock': 'Kẹt dock sạc / khóa',
      'issue.catOther': 'Sự cố khác',
      'issue.desc': 'Mô tả chi tiết',
      'issue.submit': 'Gửi báo cáo',
      'issue.success': 'Đã gửi báo cáo sự cố thành công! Mã ticket: ',
      'trip.historyTitle': 'Lịch sử chuyến đi',
      'trip.noHistory': 'Chưa có chuyến đi nào hoàn thành.',
      'trip.noActive': 'Hiện không có chuyến đi nào.',
      'trip.activeReservations': 'Đặt chỗ đang hiệu lực',
    },
  };

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  };

  function detectLang() {
    const saved = store.get(LS_LANG);
    if (SUPPORTED.includes(saved)) return saved;
    return (navigator.language || 'en').toLowerCase().startsWith('vi') ? 'vi' : 'en';
  }
  function detectTheme() {
    const saved = store.get(LS_THEME);
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  let lang = detectLang();
  let theme = detectTheme();
  document.documentElement.lang = lang;
  document.documentElement.dataset.theme = theme;   // set before first paint -> no flash

  function t(key, vars) {
    let s = (DICT[lang] && DICT[lang][key]) || DICT.en[key] || key;
    if (vars) for (const k in vars) s = s.split('{' + k + '}').join(vars[k]);
    return s;
  }

  /* Translate every [data-i18n] / [data-i18n-attr] inside root. */
  function apply(root) {
    root = root || document;
    root.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
    root.querySelectorAll('[data-i18n-attr]').forEach(el => {
      el.dataset.i18nAttr.split(',').forEach(pair => {
        const [attr, key] = pair.split(':').map(x => x.trim());
        if (attr && key) el.setAttribute(attr, t(key));
      });
    });
  }

  function setLang(next) {
    if (!SUPPORTED.includes(next) || next === lang) return;
    lang = next; store.set(LS_LANG, lang);
    document.documentElement.lang = lang;
    apply();
    document.dispatchEvent(new CustomEvent('langchange', { detail: { lang } }));
  }
  function setTheme(next) {
    theme = next === 'dark' ? 'dark' : 'light'; store.set(LS_THEME, theme);
    document.documentElement.dataset.theme = theme;
    document.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
  }

  function hubName(h) {
    const id = h && (h.hub_id || h.id);
    const key = 'hubname.' + id;
    return (DICT[lang] && DICT[lang][key]) || (h && h.name) || id || '';
  }

  document.addEventListener('DOMContentLoaded', () => apply());

  return { t, apply, setLang, setTheme, hubName, get lang() { return lang; }, get theme() { return theme; }, SUPPORTED };
})();
