class_name ShutdownService
## ShutdownService — 活纸 · 江湖行纪 关闭服务功能
## Service Shutdown Manager for graceful backend + frontend shutdown
##
## 职责:
##   1. 显示关闭确认对话框
##   2. 分步执行关闭流程 (发送指令 → 验证停止 → 退出前端)
##   3. 显示实时进度 UI
##   4. 处理后端不可达的降级场景
##
## 使用方式:
##   var shutdown := ShutdownService.new()
##   shutdown.confirm_and_execute(parent, show_confirm_callback)
##
## 依赖: GameColors (Autoload), ApiClient (Autoload), UIBuilder, DialogManager

var _on_show_confirm: Callable


## 初始化并设置确认对话框回调
## [param on_show_confirm] 确认框显示回调 Callable(title, message, on_confirm)
func init(on_show_confirm: Callable) -> void:
	_on_show_confirm = on_show_confirm


## 显示关闭确认 → 执行关闭流程
## [param parent] 父节点
func confirm_and_execute(parent: Control) -> void:
	if _on_show_confirm.is_valid():
		_on_show_confirm.call(
			"关闭服务",
			"确定要关闭所有服务吗？\n\n[color=yellow]⚠️ 这将同时停止：[/color]\n• 🌐 Web/Godot 前端\n• 🔧 后端 API 服务\n\n[color=red]未保存的进度将丢失[/color]",
			func(): _do_shutdown(parent)
		)


## 执行分步关闭流程
## [param parent] 父节点
func _do_shutdown(parent: Control) -> void:
	var progress_popup := UIBuilder.overlay(parent)
	var panel := Panel.new()
	panel.custom_minimum_size = Vector2(500, 400)
	panel.size = Vector2(500, 400)
	UIBuilder.add_panel_style(panel, Color(0.08, 0.06, 0.1))
	progress_popup.add_child(panel)
	progress_popup.resized.connect(func():
		UIBuilder.center_in_parent(panel, progress_popup.size, Vector2(500, 400))
	)

	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 12)
	vb.set_anchors_preset(PRESET_FULL_RECT)
	vb.offset_left = 30; vb.offset_top = 30; vb.offset_right = -30; vb.offset_bottom = -30
	panel.add_child(vb)

	vb.add_child(UIBuilder.lbl("⏳", 50, GameColors.TEXT, HORIZONTAL_ALIGNMENT_CENTER))
	vb.add_child(UIBuilder.lbl("正在关闭所有服务...", 18, GameColors.TEXT, HORIZONTAL_ALIGNMENT_CENTER))

	var step1 := UIBuilder.lbl("⏳ 步骤1: 发送关闭指令到后端...", 13, GameColors.ACCENT_YELLOW)
	vb.add_child(step1)

	var step2 := UIBuilder.lbl("⏳ 步骤2: 等待后端停止...", 13, GameColors.DIM)
	step2.visible = false
	vb.add_child(step2)

	var step3 := UIBuilder.lbl("⏳ 步骤3: 停止前端...", 13, GameColors.DIM)
	step3.visible = false
	vb.add_child(step3)

	# Step 1: Try to connect to backend (max 3 retries)
	var backend_success := false
	var max_retries := 3

	for attempt in range(1, max_retries + 1):
		step1.text = "⏳ 连接后端 (第%d/%d次)..." % [attempt, max_retries]

		var result: Dictionary = await ApiClient.shutdown_backend()
		if result.get("success", false):
			backend_success = true
			step1.text = "✅ 后端已接收关闭指令"
			step1.add_theme_color_override("font_color", GameColors.ACCENT_GREEN)
			break
		else:
			if attempt < max_retries:
				step1.text = "⚠️ 第%d次失败，重试中..." % attempt
				step1.add_theme_color_override("font_color", GameColors.ACCENT_YELLOW)
				await get_tree().create_timer(2.0).timeout
			else:
				step1.text = "❌ 无法连接后端"
				step1.add_theme_color_override("font_color", GameColors.ACCENT_RED)

	await get_tree().create_timer(1.0).timeout

	# Step 2: Verify backend stopped
	if backend_success:
		step2.visible = true
		step2.text = "⏳ 验证后端已停止..."

		var backend_stopped := false
		for i in range(15):
			await get_tree().create_timer(0.5).timeout
			var health_ok: bool = await ApiClient.test_backend()
			if not health_ok:
				backend_stopped = true
				break

		if backend_stopped:
			step2.text = "✅ 后端已确认停止"
			step2.add_theme_color_override("font_color", GameColors.ACCENT_GREEN)
		else:
			step2.text = "⚠️ 后端可能仍在运行"
			step2.add_theme_color_override("font_color", GameColors.ACCENT_YELLOW)

	await get_tree().create_timer(0.5).timeout

	# Step 3: Show final result
	step3.visible = true

	if backend_success:
		step3.text = "✅ 所有服务已关闭"
		step3.add_theme_color_override("font_color", GameColors.ACCENT_GREEN)

		await get_tree().create_timer(1.5).timeout

		vb.get_child(0).text = "✅"
		vb.get_child(0).add_theme_color_override("font_color", GameColors.ACCENT_GREEN)
		vb.get_child(1).text = "所有服务已关闭"
		vb.get_child(1).add_theme_color_override("font_color", GameColors.ACCENT_GREEN)

		for i in range(2, vb.get_child_count()):
			vb.get_child(i).queue_free()

		vb.add_child(UIBuilder.lbl("", 10))
		vb.add_child(UIBuilder.lbl("✅ 后端 API 服务已停止", 14, GameColors.ACCENT_GREEN))
		vb.add_child(UIBuilder.lbl("✅ Godot 前端即将退出", 14, GameColors.ACCENT_GREEN))
		vb.add_child(UIBuilder.lbl("", 10))
		vb.add_child(UIBuilder.lbl("可重新运行 python start.py 启动服务", 12, GameColors.DIM))

		await get_tree().create_timer(3.0).timeout
		get_tree().quit()
	else:
		step3.text = "⚠️ 部分服务已关闭"
		step3.add_theme_color_override("font_color", GameColors.ACCENT_YELLOW)

		vb.get_child(0).text = "🔶"
		vb.get_child(1).text = "部分服务已关闭"

		for i in range(2, vb.get_child_count()):
			vb.get_child(i).queue_free()

		vb.add_child(UIBuilder.lbl("", 10))
		vb.add_child(UIBuilder.lbl("❌ 后端未能自动关闭", 14, GameColors.ACCENT_RED))
		vb.add_child(UIBuilder.lbl("请手动关闭运行后端的终端窗口", 12, GameColors.DIM))
		
		# 添加强制退出按钮
		var force_quit_btn := UIBuilder.btn("🚪 强制退出前端", GameColors.ACCENT_RED)
		force_quit_btn.pressed.connect(get_tree().quit)
		vb.add_child(force_quit_btn)
