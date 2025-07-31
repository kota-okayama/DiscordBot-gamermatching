import React, { useState, useEffect } from 'react';

const GameActivityCalendar = () => {
  const [activities, setActivities] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // game_history.dbからデータを取得
        const response = await window.fs.readFile('game_history.db');
        const db = new SQL.Database(new Uint8Array(response));
        
        // 現在の週の開始日と終了日を計算
        const now = new Date();
        const startOfWeek = new Date(now.setDate(now.getDate() - now.getDay()));
        const endOfWeek = new Date(now.setDate(now.getDate() + 6));

        // SQLクエリでデータを取得
        const result = db.exec(`
          SELECT 
            date(start_time) as date,
            time(start_time) as start_time,
            time(end_time) as end_time,
            game_name,
            duration
          FROM game_sessions
          WHERE date(start_time) BETWEEN date('${startOfWeek.toISOString()}') 
          AND date('${endOfWeek.toISOString()}')
          ORDER BY start_time
        `);

        if (result[0] && result[0].values) {
          // データを整形
          const formattedData = formatGameData(result[0].values);
          setActivities(formattedData);
        }
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  // ゲームごとに色を割り当てる
  const gameColors = {
    'Apex Legends': 'bg-red-500',
    'Valorant': 'bg-blue-500',
    'osu!': 'bg-pink-500',
    'Minecraft': 'bg-green-500',
    'League of Legends': 'bg-purple-500',
    'Default': 'bg-gray-500'
  };

  const hours = Array.from({ length: 24 }, (_, i) => i);
  const days = ['日', '月', '火', '水', '木', '金', '土'];

  if (isLoading) {
    return <div className="flex justify-center items-center h-64">Loading...</div>;
  }

  return (
    <div className="bg-white rounded-lg shadow p-4 max-w-6xl mx-auto">
      {/* ヘッダー */}
      <div className="grid grid-cols-8 gap-2 mb-4">
        <div className="text-gray-500 text-sm"></div>
        {days.map(day => (
          <div key={day} className="text-center font-semibold">
            {day}
          </div>
        ))}
      </div>

      {/* カレンダーグリッド */}
      <div className="grid grid-cols-8 gap-2">
        {/* 時間列 */}
        <div className="space-y-8">
          {hours.map(hour => (
            <div key={hour} className="text-gray-500 text-sm text-right pr-2">
              {`${hour.toString().padStart(2, '0')}:00`}
            </div>
          ))}
        </div>

        {/* 各曜日の列 */}
        {days.map((day, dayIndex) => (
          <div key={day} className="relative space-y-2">
            {/* 時間枠 */}
            {hours.map(hour => (
              <div 
                key={hour}
                className="h-8 border-t border-gray-200 relative"
              />
            ))}

            {/* イベント */}
            {activities
              .filter(activity => new Date(activity.date).getDay() === dayIndex)
              .map((activity, index) => (
                activity.events.map((event, eventIndex) => {
                  const startHour = parseInt(event.startTime.split(':')[0]);
                  const endHour = parseInt(event.endTime.split(':')[0]);
                  const duration = endHour - startHour;
                  const top = startHour * 34;
                  
                  return (
                    <div
                      key={`${index}-${eventIndex}`}
                      className={`absolute left-0 right-0 mx-1 rounded px-2 py-1 text-xs text-white ${gameColors[event.game] || gameColors.Default}`}
                      style={{
                        top: `${top}px`,
                        height: `${duration * 34 - 4}px`
                      }}
                    >
                      {event.game}
                      <br />
                      {event.startTime}-{event.endTime}
                    </div>
                  );
                })
              ))}
          </div>
        ))}
      </div>

      {/* 凡例 */}
      <div className="mt-4 border-t border-gray-200 pt-4">
        <h3 className="text-sm font-semibold mb-2">ゲーム凡例</h3>
        <div className="flex flex-wrap gap-4">
          {Object.entries(gameColors).map(([game, color]) => (
            game !== 'Default' && (
              <div key={game} className="flex items-center">
                <div className={`w-4 h-4 ${color} rounded mr-2`}></div>
                <span className="text-sm">{game}</span>
              </div>
            )
          ))}
        </div>
      </div>
    </div>
  );
};

// データベースから取得したデータを整形する関数
const formatGameData = (rawData) => {
  const formattedData = [];
  
  rawData.forEach(([date, startTime, endTime, gameName]) => {
    const dayData = formattedData.find(d => d.date === date);
    
    if (dayData) {
      dayData.events.push({
        game: gameName,
        startTime: startTime.slice(0, 5),  // HH:MM形式に整形
        endTime: endTime.slice(0, 5)
      });
    } else {
      formattedData.push({
        date,
        events: [{
          game: gameName,
          startTime: startTime.slice(0, 5),
          endTime: endTime.slice(0, 5)
        }]
      });
    }
  });
  
  return formattedData;
};

export default GameActivityCalendar;