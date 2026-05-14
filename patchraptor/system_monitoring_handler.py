import asyncio
import datetime
import os
import discord
from .log_manager import logger, LOG_PATH
from .base_handler import BaseHandler
import tempfile

class SystemMonitoringHandler(BaseHandler):
    """Handles diagnostic and monitoring commands: status, analytics, diagnose"""
    
    async def cmd_status(self, message, content: str, content_lower: str):
        """Handle .status command - show system and server status with analytics overview"""
        logger.info_command(".status received")
        
        state = self.telemetry_manager.current_state
        diag = await self.telemetry_manager.get_diagnostics()
        
        embed = discord.Embed(title="📊 **Host Status Dashboard**", color=0x3498DB)
        embed.description = (
            f"🔌 PC Uptime     : {diag['uptime_pc']}\n"
            f"💻 System CPU    : {diag['cpu_usage']:.1f}%\n"
            f"⚡ Memory Usage  : {diag['ram_used']:.2f}/{diag['ram_total']:.2f} GB\n"
            f"💾 Disk Usage    : {diag['disk_info']['used']:.1f}/{diag['disk_info']['total']:.1f} GB ({diag['disk_info']['percent']:.1f}%)\n"
            f"📈 7-Day Avg     : {state.total_7day_uptime_avg:.1f}% Uptime | {state.total_7day_player_avg:.1f} Players"
        )
        
        await self.discord_manager.send_temp_message(message.channel, embed=embed)

    async def cmd_analytics(self, message, content: str, content_lower: str):
        """Handle .analytics command - show deep historical performance and player trends"""
        logger.info_command(".analytics received")
        
        state = self.telemetry_manager.current_state
        peak_players = self.telemetry_manager.player_stats_tracker.get_7day_peak()
        rolling_perf = self.telemetry_manager.performance_tracker.get_rolling_averages()
        
        embed = discord.Embed(title="📈 Cluster Analytics Dashboard", color=0x3498DB)
        embed.set_footer(text=f"Data compiled from the last 7 days")
        
        # Player Trends
        embed.add_field(
            name="🎮 Player Vitality", 
            value=f"• 7-Day Peak: {peak_players} players\n"
                  f"• 7-Day Average: {state.total_7day_player_avg:.1f} players\n"
                  f"• Current Total: {state.total_players} players",
            inline=False
        )
        
        # Uptime / Reliability
        uptime = state.total_7day_uptime_avg
        grade = "Optimal" if uptime > 99 else "Stable" if uptime > 95 else "Caution"
        embed.add_field(
            name="🕒 Reliability Score",
            value=f"• Average Uptime: {uptime:.1f}%\n"
                  f"• System Health: {grade}",
            inline=False
        )
        
        # Hardware Trends (Rolling Averages)
        embed.add_field(
            name="💻 Performance Trends",
            value=f"• Average CPU Load: {rolling_perf['cpu']:.1f}%\n"
                  f"• Average RAM Load: {rolling_perf['ram']:.1f}%\n"
                  f"• Disk Occupancy: {rolling_perf['disk']:.1f}%",
            inline=False
        )
        
        await self.discord_manager.send_temp_message(message.channel, embed=embed)

    async def cmd_diagnose(self, message, content: str, content_lower: str):
        """Handle .diagnose command - perform bot health check via TelemetryManager"""
        logger.info_command(".diagnose received")
        embed = discord.Embed(title="Bot Health Diagnostic", color=0x99AAB5)
        
        diag = await self.telemetry_manager.get_diagnostics()
        
        embed.add_field(name="Health Check Results", value="\n".join(diag['results']), inline=False)
        
        if diag['issues']:
            embed.add_field(name="Issues Found", value="\n".join(f"• {issue}" for issue in diag['issues']), inline=False)
        else:
            embed.add_field(name="Status", value="☑️ All systems operational", inline=False)
        
        await self.discord_manager.send_temp_message(message.channel, embed=embed)

    async def cmd_check(self, message, content: str, content_lower: str):
        """Handle .check command - check for updates"""
        logger.info_command(".check received")
        try:
            current = self.version_manager.get_current_version()
            latest = await self.version_manager.get_latest_build_id()
            
            if not latest:
                await self.discord_manager.send_temp_message(message.channel, "⚠️ Unable to fetch latest version from Steam.")
                return
            
            if current == latest:
                await self.discord_manager.send_temp_message(message.channel, f"☑️ Server is up to date (Build {current})")
            else:
                await self.discord_manager.send_temp_message(message.channel, f"🔄 Update available: Build {current} → {latest}")
        except Exception as e:
            await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to check for updates: {e}")
    
    async def cmd_debug(self, message, content: str, content_lower: str):
        """Handle .debug command - toggle debug logging"""
        logger.info_command(".debug received")
        new_state = logger.toggle_debug()
        status = "☑️ ON" if new_state else "🔲 OFF"
        await self.discord_manager.send_temp_message(message.channel, f"🐛 Debug logging is now **{status}**")

    async def cmd_report(self, message, content: str, content_lower: str):
        """Handle .report command - generate status report from logs"""
        logger.info_command(".report received")
        
        try:
            # Get all patchraptor log files
            log_files = [os.path.join(LOG_PATH, f) for f in os.listdir(LOG_PATH) if f.startswith('patchraptor_') and f.endswith('.log')]
            if not log_files:
                await self.discord_manager.send_temp_message(message.channel, "⚠️ No log files found.")
                return
            
            log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            all_lines = []
            for log_file in log_files[:3]:
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        all_lines.extend(f.readlines()[-50:])
                except Exception: continue
            
            if not all_lines:
                await self.discord_manager.send_temp_message(message.channel, "⚠️ No log content found.")
                return
            
            report_content = "".join(all_lines)
            
            # Use temp file for upload
            with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as temp_file:
                temp_file.write(report_content)
                temp_file_path = temp_file.name
            
            await self.discord_manager.send_temp_message(
                message.channel,
                content="📋 **PatchRaptor Log Report**",
                file=discord.File(temp_file_path, filename='patchraptor_report.log')
            )
            os.unlink(temp_file_path)
        except Exception as e:
            logger.error_system(f"Failed to generate report: {e}")
            await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to generate report: {e}")
