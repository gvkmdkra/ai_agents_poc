import pandas as pd
import streamlit as st
from datetime import datetime

def render_monitor():
    st.markdown("### 📊 Campaign Analytics & Monitoring")
    st.markdown("Track performance, view logs, and analyze campaign effectiveness")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if "campaign_logs" in st.session_state and st.session_state.campaign_logs:
        logs = st.session_state.campaign_logs
        
        # Key Metrics Section
        st.markdown("#### 📈 Key Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_campaigns = len(logs)
            st.metric("Total Campaigns", total_campaigns, delta=f"+{total_campaigns}", delta_color="normal")
        with col2:
            total_sent = sum(log.get("sent", 0) for log in logs)
            st.metric("Messages Delivered", f"{total_sent:,}", delta="Success")
        with col3:
            sms_campaigns = len([l for l in logs if l.get("type") == "SMS"])
            st.metric("SMS Campaigns", sms_campaigns, delta=f"{sms_campaigns}")
        with col4:
            email_campaigns = len([l for l in logs if l.get("type") == "Email"])
            st.metric("Email Campaigns", email_campaigns, delta=f"{email_campaigns}")
        st.divider()
        
        # Campaign History Section
        st.markdown("#### 📜 Campaign History")
        
        logs_data = []
        for i, log in enumerate(logs, 1):
            logs_data.append({
                "#": i,
                "Timestamp": log.get("time", "N/A"),
                "Channel": log.get("type", "N/A"),
                "Targets": log.get("targets", log.get("sent", 0)),
                "Delivered": log.get("sent", 0),
                "Failed": log.get("failed", 0),
                "Status": log.get("status", "✅ Success"),
                "Query": log.get("query", "N/A")[:50] + "..." if len(log.get("query", "")) > 50 else log.get("query", "N/A")
            })
        
        logs_df = pd.DataFrame(logs_data)
        
        # Filter controls
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            filter_type = st.selectbox(
                "Filter Channel", 
                ["All", "SMS", "Email", "Call"], 
                key="log_filter"
            )
        
        filtered_df = logs_df[logs_df["Channel"] == filter_type] if filter_type != "All" else logs_df
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Action buttons
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Export Logs",
                data=csv,
                file_name=f"campaign_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col2:
            if st.button("🗑️ Clear Logs", use_container_width=True):
                if st.session_state.get("confirm_clear"):
                    st.session_state.campaign_logs = []
                    st.session_state.confirm_clear = False
                    st.success("✅ Logs cleared!")
                    st.rerun()
                else:
                    st.session_state.confirm_clear = True
                    st.warning("⚠️ Click again to confirm")
        st.divider()
        
        # Performance Analytics
        st.markdown("#### 📈 Performance Overview")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### Delivery Success Rate")
            total_attempted = sum(log.get("sent", 0) + log.get("failed", 0) for log in logs)
            success_rate = (total_sent / total_attempted * 100) if total_attempted > 0 else 0
            st.progress(success_rate / 100)
            st.metric("Overall Success", f"{success_rate:.1f}%", delta="High Performance" if success_rate > 90 else "Good")
        
        with col2:
            st.markdown("##### Recent Campaign Activity")
            recent_logs = logs[-5:] if len(logs) >= 5 else logs
            for log in reversed(recent_logs):
                status_icon = "✅" if log.get("status") != "Failed" else "❌"
                st.caption(f"{status_icon} {log.get('type')} • {log.get('sent', 0)} sent • {log.get('time', '')[:16]}")
        st.divider()
        
        # Campaign Breakdown
        st.markdown("#### 📊 Campaign Distribution")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### By Channel Type")
            call_campaigns = len([l for l in logs if l.get("type") == "Call"])
            type_counts = {
                "📱 SMS": sms_campaigns,
                "📧 Email": email_campaigns,
                "📞 Call": call_campaigns
            }
            for ctype, count in type_counts.items():
                if count > 0:
                    percentage = (count / total_campaigns * 100) if total_campaigns > 0 else 0
                    st.write(f"**{ctype}**: {count} campaigns ({percentage:.0f}%)")
                    st.progress(percentage / 100)
        
        with col2:
            st.markdown("##### Message Volume Timeline")
            time_data = {}
            for log in logs:
                date = log.get("time", "").split()[0]
                if date:
                    time_data[date] = time_data.get(date, 0) + log.get("sent", 0)
            if time_data:
                for date, count in sorted(time_data.items())[-7:]:
                    st.caption(f"📅 **{date}**: {count:,} messages")
    else:
        # Empty state with better design
        st.markdown("""
        <div style="text-align: center; padding: 3rem 2rem; background: linear-gradient(135deg, #667eea22 0%, #764ba222 100%); border-radius: 12px; margin: 2rem 0;">
            <h3 style="color: #667eea;">📭 No Campaign Data Yet</h3>
            <p style="color: #5F6368;">Launch your first campaign to start tracking performance and analytics</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            <div style="padding: 1.5rem; background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                <h4>📊 Real-time Metrics</h4>
                <p style="color: #5F6368; font-size: 0.9rem;">Track campaign performance with live dashboards and KPIs</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div style="padding: 1.5rem; background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                <h4>📜 Detailed History</h4>
                <p style="color: #5F6368; font-size: 0.9rem;">View complete logs of all campaigns and their results</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div style="padding: 1.5rem; background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                <h4>📥 Export & Analyze</h4>
                <p style="color: #5F6368; font-size: 0.9rem;">Download logs and analyze campaign effectiveness</p>
            </div>
            """, unsafe_allow_html=True)


