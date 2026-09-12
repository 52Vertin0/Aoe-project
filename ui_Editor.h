/********************************************************************************
** Form generated from reading UI file 'Editor.ui'
**
** Created by: Qt User Interface Compiler version 5.9.2
**
** WARNING! All changes made in this file will be lost when recompiling UI file!
********************************************************************************/

#ifndef UI_EDITOR_H
#define UI_EDITOR_H

#include <QtCore/QVariant>
#include <QtWidgets/QAction>
#include <QtWidgets/QApplication>
#include <QtWidgets/QButtonGroup>
#include <QtWidgets/QComboBox>
#include <QtWidgets/QHeaderView>
#include <QtWidgets/QPushButton>
#include <QtWidgets/QWidget>

QT_BEGIN_NAMESPACE

class Ui_Editor
{
public:
    QPushButton *export_map;
    QComboBox *land_height;
    QComboBox *player_building_and_source;
    QComboBox *ai_building_and_resource;
    QComboBox *player_human;
    QComboBox *ai_human;
    QComboBox *resource;
    QComboBox *animal;
    QPushButton *delete_object;
    QComboBox *land_type;
    QComboBox *patrolArea;
    QPushButton *mouse_button;
    QComboBox *enemyStatus;

    void setupUi(QWidget *Editor)
    {
        if (Editor->objectName().isEmpty())
            Editor->setObjectName(QStringLiteral("Editor"));
        Editor->resize(1500, 300);
        export_map = new QPushButton(Editor);
        export_map->setObjectName(QStringLiteral("export_map"));
        export_map->setGeometry(QRect(0, 40, 111, 51));
        land_height = new QComboBox(Editor);
        land_height->setObjectName(QStringLiteral("land_height"));
        land_height->setGeometry(QRect(330, 40, 91, 51));
        player_building_and_source = new QComboBox(Editor);
        player_building_and_source->setObjectName(QStringLiteral("player_building_and_source"));
        player_building_and_source->setGeometry(QRect(420, 40, 131, 51));
        ai_building_and_resource = new QComboBox(Editor);
        ai_building_and_resource->setObjectName(QStringLiteral("ai_building_and_resource"));
        ai_building_and_resource->setGeometry(QRect(660, 40, 111, 51));
        player_human = new QComboBox(Editor);
        player_human->setObjectName(QStringLiteral("player_human"));
        player_human->setGeometry(QRect(550, 40, 111, 51));
        ai_human = new QComboBox(Editor);
        ai_human->setObjectName(QStringLiteral("ai_human"));
        ai_human->setGeometry(QRect(770, 40, 141, 51));
        resource = new QComboBox(Editor);
        resource->setObjectName(QStringLiteral("resource"));
        resource->setGeometry(QRect(990, 40, 111, 51));
        animal = new QComboBox(Editor);
        animal->setObjectName(QStringLiteral("animal"));
        animal->setGeometry(QRect(910, 40, 81, 51));
        delete_object = new QPushButton(Editor);
        delete_object->setObjectName(QStringLiteral("delete_object"));
        delete_object->setGeometry(QRect(110, 40, 111, 51));
        land_type = new QComboBox(Editor);
        land_type->setObjectName(QStringLiteral("land_type"));
        land_type->setGeometry(QRect(220, 40, 111, 51));
        patrolArea = new QComboBox(Editor);
        patrolArea->setObjectName(QStringLiteral("patrolArea"));
        patrolArea->setEnabled(false);
        patrolArea->setGeometry(QRect(1211, 40, 111, 51));
        patrolArea->setEditable(false);
        mouse_button = new QPushButton(Editor);
        mouse_button->setObjectName(QStringLiteral("mouse_button"));
        mouse_button->setGeometry(QRect(0, 100, 111, 51));
        enemyStatus = new QComboBox(Editor);
        enemyStatus->setObjectName(QStringLiteral("enemyStatus"));
        enemyStatus->setEnabled(false);
        enemyStatus->setGeometry(QRect(1321, 40, 111, 51));
        enemyStatus->setEditable(false);

        retranslateUi(Editor);

        QMetaObject::connectSlotsByName(Editor);
    } // setupUi

    void retranslateUi(QWidget *Editor)
    {
        Editor->setWindowTitle(QApplication::translate("Editor", "Form", Q_NULLPTR));
        export_map->setText(QApplication::translate("Editor", "\345\257\274\345\207\272\345\234\260\345\233\276", Q_NULLPTR));
        land_height->clear();
        land_height->insertItems(0, QStringList()
         << QApplication::translate("Editor", "\345\234\260\347\232\256\351\253\230\345\272\246", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\217\220\345\215\207\351\253\230\345\272\246", Q_NULLPTR)
         << QApplication::translate("Editor", "\351\231\215\344\275\216\351\253\230\345\272\246", Q_NULLPTR)
        );
        player_building_and_source->clear();
        player_building_and_source->insertItems(0, QStringList()
         << QApplication::translate("Editor", "\347\216\251\345\256\266\350\265\204\346\272\220/\345\273\272\347\255\221", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\350\260\267\344\273\223", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\346\210\277\345\255\220", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\345\270\202\344\270\255\345\277\203", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\350\277\220\350\276\223\350\210\271", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\346\270\224\345\234\272", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\346\210\230\350\210\271", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\350\210\271\345\235\236", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\346\270\224\350\210\271", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\344\273\223\345\272\223", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\347\256\255\345\241\224", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\345\205\265\350\220\245", Q_NULLPTR)
        );
        ai_building_and_resource->clear();
        ai_building_and_resource->insertItems(0, QStringList()
         << QApplication::translate("Editor", "\346\225\214\346\226\271\350\265\204\346\272\220/\345\273\272\347\255\221", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\346\255\246\345\231\250\346\224\273\345\237\216\345\216\202", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\346\212\225\347\237\263\350\275\246", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\347\256\255\345\241\224", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\346\210\230\350\210\271", Q_NULLPTR)
        );
        player_human->clear();
        player_human->insertItems(0, QStringList()
         << QApplication::translate("Editor", "\347\216\251\345\256\266\344\272\272\347\211\251", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\350\213\261\351\233\204\347\245\255\345\217\270", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\345\206\234\346\260\221", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\346\243\215\346\243\222\345\205\265", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\346\226\247\345\244\264\345\205\265", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\344\276\246\345\257\237\345\205\265", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\216\251\345\256\266\345\274\223\347\256\255\346\211\213", Q_NULLPTR)
        );
        ai_human->clear();
        ai_human->insertItems(0, QStringList()
         << QApplication::translate("Editor", "\346\225\214\346\226\271\344\272\272\347\211\251", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\351\252\221\345\205\265", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\346\212\225\347\237\263\350\275\246", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\346\226\271\351\230\265\345\205\265", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\351\251\267\351\251\254\346\210\230\350\275\246", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\351\230\224\345\211\221\345\205\265", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\345\244\215\345\220\210\345\274\223\346\211\213", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\346\210\230\350\275\246\345\260\204\346\211\213", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\347\245\255\345\217\270", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\346\243\215\346\243\222\345\205\265", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\346\226\247\345\244\264\345\205\265", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\345\274\223\347\256\255\346\211\213", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\225\214\346\226\271\344\276\246\345\257\237\345\205\265", Q_NULLPTR)
        );
        resource->clear();
        resource->insertItems(0, QStringList()
         << QApplication::translate("Editor", "\345\205\254\347\253\213\350\265\204\346\272\220", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\265\206\346\236\234", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\240\221\346\234\250", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\237\263\345\244\264", Q_NULLPTR)
         << QApplication::translate("Editor", "\351\207\221\347\237\277", Q_NULLPTR)
        );
        resource->setCurrentText(QApplication::translate("Editor", "\345\205\254\347\253\213\350\265\204\346\272\220", Q_NULLPTR));
        animal->clear();
        animal->insertItems(0, QStringList()
         << QApplication::translate("Editor", "\345\212\250\347\211\251", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\236\252\347\276\232", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\213\256\345\255\220", Q_NULLPTR)
         << QApplication::translate("Editor", "\345\244\247\350\261\241", Q_NULLPTR)
        );
        delete_object->setText(QApplication::translate("Editor", "\345\210\240\351\231\244\345\257\271\350\261\241", Q_NULLPTR));
        land_type->clear();
        land_type->insertItems(0, QStringList()
         << QApplication::translate("Editor", "\345\234\260\347\232\256\347\261\273\345\236\213", Q_NULLPTR)
         << QApplication::translate("Editor", "\350\215\211\345\234\260", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\265\267\346\264\213", Q_NULLPTR)
        );
        patrolArea->clear();
        patrolArea->insertItems(0, QStringList()
         << QApplication::translate("Editor", "\345\267\241\351\200\273\345\214\272\345\237\237", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\233\262\347\272\277\345\214\272\345\237\237", Q_NULLPTR)
         << QApplication::translate("Editor", "\345\234\206\345\275\242\345\214\272\345\237\237", Q_NULLPTR)
         << QApplication::translate("Editor", "\347\237\251\345\275\242\345\214\272\345\237\237", Q_NULLPTR)
        );
        patrolArea->setCurrentText(QApplication::translate("Editor", "\345\267\241\351\200\273\345\214\272\345\237\237", Q_NULLPTR));
        mouse_button->setText(QApplication::translate("Editor", "\351\274\240\346\240\207", Q_NULLPTR));
        enemyStatus->clear();
        enemyStatus->insertItems(0, QStringList()
         << QApplication::translate("Editor", "\346\225\214\344\272\272\347\212\266\346\200\201", Q_NULLPTR)
         << QApplication::translate("Editor", "\346\224\273\345\207\273", Q_NULLPTR)
         << QApplication::translate("Editor", "\351\230\262\345\256\210", Q_NULLPTR)
        );
        enemyStatus->setCurrentText(QApplication::translate("Editor", "\346\225\214\344\272\272\347\212\266\346\200\201", Q_NULLPTR));
    } // retranslateUi

};

namespace Ui {
    class Editor: public Ui_Editor {};
} // namespace Ui

QT_END_NAMESPACE

#endif // UI_EDITOR_H
